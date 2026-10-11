"""
This file handles the views to be displayed to students, routing from the URL paths to the HTML templates.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ExpressionWrapper, F, FloatField
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from curriculum import graph
from curriculum.models import MacroDomain, MicroSkill
from ml_engine import bkt, diagnostic, recommender, services

from .models import MasterySnapshot, PracticeSession, SkillMastery

# Constants for the activity history page
ACTIVITY_INITIAL = 5
ACTIVITY_INCREMENT = 10

# The tiers for each session
SCORE_TIER_STRONG = 0.8
SCORE_TIER_WEAK = 0.4

# A function that routes the landing page when users visit the site
def landing(request):

    # For authenticated users
    if request.user.is_authenticated:

        # Teachers are redirected to teacher dashboard
        if request.user.is_teacher:
            return redirect("classes:teacher_dashboard")

        # Students are redirected to student dashboard
        return redirect("learning:dashboard")

    # For unauthenticated users, render the landing page
    return render(request, "landing.html")


# A function to extract the details of all skills for a given student
def _skill_rows(student):

    # Retrieve the mastery level for all skills for the student
    masteries = {
        m.micro_skill_id: m
        for m in SkillMastery.objects.filter(student=student)
    }

    # Retrieve the IDs of the hidden skills
    hidden = services.hidden_skill_ids(student)
    rows = []

    # Retrieve all active micro skills
    skills = (
        MicroSkill.objects.filter(is_active=True)
        .select_related("macro_domain")
        .prefetch_related("prerequisites")
        .order_by("form_level", "order")
    )

    # Loop through each skill
    for skill in skills:

        # Retrieve the state for the current skill
        mastery = masteries.get(skill.id)
        state = services.skill_state(student, skill, mastery)

        # Add the details to rows
        rows.append(
            {
                "skill": skill,
                "mastery": mastery,
                "state": state,
                "mastery_percent": mastery.mastery_percent if mastery else 0,
                "level_label": mastery.level_label if mastery and mastery.attempts else "Not started",
                "unmet": services.unmet_prerequisites(student, skill) if state == "locked" else [],
                "hidden": skill.id in hidden,
            }
        )

    # Return the list of skill details
    return rows


# A function to render the student main dashboard
@login_required
def dashboard(request):

    # Teachers are redirected to their teacher dashboard
    if request.user.is_teacher:
        return redirect("classes:teacher_dashboard")

    # Get the student object with their profiles and skill details
    student = request.user
    services.get_profile(student)
    rows = _skill_rows(student)

    # Categorize skills into unlocked and mastered
    visible = [r for r in rows if not r["hidden"]]
    unlocked = [r for r in visible if r["state"] != "locked"]
    mastered = [r for r in visible if r["state"] == "mastered"]

    # Perform recommendation for the student
    ranked = recommender.recommend_next_skills(student, n=50)

    # Get the top recommended skill with the mastery level
    rec_skill = ranked[0][0] if ranked else None
    rec_mastery = ranked[0][2] if ranked else None

    # Get the next two recommendations for review notes
    review_lessons = [{"skill": s, "mastery": m} for s, _score, m in ranked[1:3]]

    # If the recommender does not provide enough recommendations
    if len(review_lessons) < 2:

        # Exclude the recommended skill and the chapters already in review notes
        exclude_ids = {rec_skill.id} if rec_skill else set()
        exclude_ids |= {r["skill"].id for r in review_lessons}

        # Only retain the skills that are unlocked
        allowed_ids = {r["skill"].id for r in unlocked}

        # Pick the skills they have attempted but not touched longest ago
        stale = (
            SkillMastery.objects.filter(
                student=student, attempts__gt=0, micro_skill_id__in=allowed_ids
            )
            .exclude(micro_skill_id__in=exclude_ids)
            .select_related("micro_skill")
            .order_by("last_attempt_at")[: 2 - len(review_lessons)]
        )

        # And add the skills to the review notes
        review_lessons += [{"skill": m.micro_skill, "mastery": m} for m in stale]

    # Extract the top six skills
    skillset = _skillset(visible)

    # Compile all information together
    context = {
        "unlocked_count": len(unlocked),
        "total_count": len(visible),
        "mastered_count": len(mastered),
        "overall_mastery": round(services.overall_mastery(student) * 100),
        "hours_week_display": _fmt_hours(services.hours_this_week(student)),
        "hours_all_display": _fmt_hours(services.hours_all_time(student)),
        "rec_skill": rec_skill,
        "rec_mastery": rec_mastery,
        "review_lessons": review_lessons,
        "skillset": skillset["top"],
        "skillset_all": skillset["all"],
        "memberships": student.class_memberships.filter(is_active=True).select_related(
            "school_class", "school_class__teacher"
        ),
        "has_history": PracticeSession.objects.filter(student=student, is_complete=True).exists(),
    }

    # Lastly, pass to the dashboard HTML to render
    return render(request, "student/dashboard.html", context)


# A function to format time into hours or minutes
def _fmt_hours(hours):

    # Show hours if period is more than 1 hour
    if hours >= 1:
        return f"{hours:.1f}h"

    # Otherwise, show minutes
    minutes = round(hours * 60)
    return f"{minutes}m"


# A function to extract the top skills for the dashboard
def _skillset(rows):

    # Extract the domain and their corresponding skills
    by_domain = {}
    for r in rows:
        by_domain.setdefault(r["skill"].macro_domain_id, []).append(r)

    # Loop through each macro domain
    domains = []
    for domain in MacroDomain.objects.order_by("order"):

        # Retrieve the skill details for the current domain
        domain_rows = by_domain.get(domain.id, [])
        if not domain_rows:
            continue

        # Keep only rows with mastery level and at least one attempt
        attempted = [r for r in domain_rows if r["mastery"] and r["mastery"].attempts]

        # Calculate the average mastery value
        percent = (
            bkt.to_percent(sum(r["mastery"].bkt_mastery for r in attempted) / len(attempted))
            if attempted
            else 0
        )

        # Find the last attempt timestamp for the domain
        last_attempt = max(
            (r["mastery"].last_attempt_at for r in attempted if r["mastery"].last_attempt_at),
            default=None,
        )

        # Add the details to the domain list
        domains.append(
            {
                "domain": domain,
                "percent": percent,
                "skills": len(domain_rows),
                "skill_rows": domain_rows,
                "last_attempt": last_attempt,
            }
        )

    # Sort the domains by mastery percent, then last attempt, then skills
    top = sorted(
        (
            {
                "skill": row["skill"],
                "percent": row["mastery_percent"]
                if row["mastery"] and row["mastery"].attempts
                else 0,
                "last_attempt": row["mastery"].last_attempt_at
                if row["mastery"] and row["mastery"].attempts
                else None,
            }
            for row in rows
        ),
        key=lambda row: (
            -row["percent"],
            -(row["last_attempt"].timestamp() if row["last_attempt"] else 0),
            row["skill"].form_level,
            row["skill"].order,
            row["skill"].title,
        ),
    )[:6]                                       # Extract top 6 skills for dashboard

    # Lastly, return both the top skills and all skills grouped by domains
    return {"top": top, "all": domains}


# A function to render the learning path for the student
@login_required
def learning_path(request):

    # Redirect teachers to their dashboard
    if request.user.is_teacher:
        return redirect("classes:teacher_dashboard")

    # Get the student object and their skill details
    student = request.user
    rows = _skill_rows(student)

    # Determine if the full view is requested and filter the rows accordingly
    full = request.GET.get("view") == "full"
    shown = [r for r in rows if not r["hidden"]] if full else _concise_rows(rows)

    # Build the learning path
    diagram = graph.build_graph(shown)

    # Change the edges to locked if either the source or target card is locked
    by_slug = {r["skill"].slug: r for r in shown}
    for edge in diagram["edges"]:
        ends = (by_slug.get(edge["source"]), by_slug.get(edge["target"]))
        edge["locked"] = any(row and row["state"] == "locked" for row in ends)

    # Pass the diagram to the HTML template to render
    return render(
        request,
        "student/learning_path.html",
        {"graph": diagram, "full": full},
    )


# A function to only show unlocked skills and the next locked skill in the learning path
def _concise_rows(rows):

    # Extract the skills with their IDs
    by_id = {r["skill"].id: r for r in rows}

    # Loop through each skill in prerequisite order
    visible = {}
    for row in graph.in_prerequisite_order(rows):

        # Extract the skill and its prerequisites
        skill = row["skill"]
        prerequisites = [by_id[p.id] for p in skill.prerequisites.all() if p.id in by_id]

        # Completely hide the skill if the skill is hidden
        if row["hidden"]:
            visible[skill.id] = False

        # Show all unlocked skills
        elif row["state"] != "locked":
            visible[skill.id] = True

        # Show the skill if all its prerequisites are visible and unlocked
        else:
            visible[skill.id] = all(
                visible.get(p["skill"].id, False) and p["state"] != "locked"
                for p in prerequisites
            )

    # Lastly, return the visible skills
    return [r for r in rows if visible.get(r["skill"].id)]


# A function to render the details of a skill
@login_required
def skill_detail(request, slug):

    # Redirect teachers to their dashboard
    if request.user.is_teacher:
        return redirect("classes:teacher_dashboard")

    # If the request is not an AJAX request, redirect users to the learning path page
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return redirect("learning:learning_path")

    # Extract student and skill details
    student = request.user
    skill = get_object_or_404(
        MicroSkill.objects.select_related("macro_domain"), slug=slug, is_active=True
    )
    mastery = SkillMastery.objects.filter(student=student, micro_skill=skill).first()
    state = services.skill_state(student, skill, mastery)
    unmet = services.unmet_prerequisites(student, skill)

    # Compile the context and render the skill detail pop up
    context = {
        "skill": skill,
        "mastery": mastery,
        "state": state,
        "unmet": unmet,
    }
    return render(request, "student/_skill_detail_modal.html", context)


# A function to display the review notes of a skill
@login_required
def learn_notes(request, slug):

    # Redirect teachers to their dashboard
    if request.user.is_teacher:
        return redirect("classes:teacher_dashboard")

    # Extract student and skill details
    student = request.user
    skill = get_object_or_404(MicroSkill, slug=slug, is_active=True)
    mastery = services.get_mastery(student, skill)

    # If the student hasn't viewed the notes before, mark it as viewed
    if not mastery.notes_viewed:
        mastery.notes_viewed = True
        mastery.save(update_fields=["notes_viewed"])

    # Compile the context and render the review notes page
    context = {
        "skill": skill,
        "note": getattr(skill, "note", None),
        "examples": skill.worked_examples.all(),
    }
    return render(request, "student/learn_notes.html", context)


# A function to start a quiz set for a skill
@login_required
def practice_start(request, slug):

    # Redirect teachers to their dashboard
    if request.user.is_teacher:
        return redirect("classes:teacher_dashboard")

    # Extract student and skill details
    student = request.user
    skill = get_object_or_404(MicroSkill, slug=slug, is_active=True)

    # If the skill is still locked, redirect students to skill detail page
    if not services.is_micro_skill_unlocked(student, skill):
        messages.info(request, "That skill is still locked. Master its prerequisites first.")
        return redirect("learning:skill_detail", slug=slug)

    # Retrieve the mastery level for the skill and create a new practice session
    mastery = services.get_mastery(student, skill)
    session = PracticeSession.objects.create(
        student=student,
        micro_skill=skill,
        kind=PracticeSession.Kind.PRACTICE,
        total_questions=settings.PRACTICE_SET_SIZE,
        mastery_before=mastery.bkt_mastery,
    )

    # Then redirect students to the practice question page
    return redirect("learning:practice_question", session_id=session.id)


# A function to show questions in a practice session
@login_required
def practice_question(request, session_id):

    # Verify if the session belongs to the student
    session = _get_owned_session(request, session_id)

    # If the session is completed, redirect to the results page
    if session.is_complete:
        return redirect("learning:practice_results", session_id=session.id)

    # If the session has no associated micro-skill (admin removes the skill when students attempt), it is marked as an abandoned session
    if session.micro_skill is None:
        return _abandon_skill_less_session(session)

    # If the session does not have a question, let the recommender choose the next question
    if session.current_question is None or session.current_question.micro_skill_id != session.micro_skill_id:
        choice = recommender.choose_next_question(session)

        # If the recommender cannot find a question, return to the skill detail page (but should not happen in practice)
        if choice is None:
            messages.info(request, "No practice questions are available for this skill yet.")
            return redirect("learning:skill_detail", slug=session.micro_skill.slug)

        # Update the session with the chosen question and save into database
        session.current_question = choice.question
        session.current_predicted_prob = choice.p_correct
        session.current_proximity = choice.recommendation_score
        session.save(
            update_fields=[
                "current_question",
                "current_predicted_prob",
                "current_proximity",
            ]
        )

    # Determine the number of questions answered in this quiz set
    answered = session.answered_count

    # Compile details and send to HTML template to render
    context = {
        "session": session,
        "question": session.current_question,
        "answer_choices": session.current_question.choices_in_display_order(session.id),
        "question_number": session.next_question_number,
        "answered_count": answered,
        "progress_percent": round(answered / session.total_questions * 100),
    }
    return render(request, "student/practice.html", context)


# A function to record submitted answers and progress to the next question
@login_required
@require_POST
def practice_answer(request, session_id):

    # Verify if the session belongs to the student
    session = _get_owned_session(request, session_id)

    # If the session has no associated micro-skill (admin removes the skill when students attempt), it is marked as an abandoned session
    if session.micro_skill is None:
        return _abandon_skill_less_session(session)

    # If the session is already completed or has no current question, redirect to the next question
    if session.is_complete or session.current_question is None:
        return redirect("learning:practice_question", session_id=session.id)

    # Record the current question and the submitted answer
    question = session.current_question
    submitted = request.POST.get("answer", "")

    # Record the attempt and check if the answer is correct
    _, is_correct = services.record_attempt(
        request.user,
        question,
        submitted,
        session=session,
        predicted_prob=session.current_predicted_prob,
        proximity_score=session.current_proximity,
        response_time_sec=_response_time(request),
    )

    # Update the session score if answer is correct
    if is_correct:
        session.score += 1

    # Reset the current question
    session.current_question = None
    session.current_predicted_prob = None
    session.current_proximity = None

    # If students finish answering all questions in the set, save the mastery snapshot
    if session.answered_count >= session.total_questions:
        _finalise_session(session)

    # If not, save the session
    else:
        session.save()

    # If the session is completed, redirect to the result page
    if session.is_complete:
        return redirect("learning:practice_results", session_id=session.id)

    # If not, redirect to the next question
    return redirect("learning:practice_question", session_id=session.id)


# A function to let a student leave a practice set early while retaining attempts
@login_required
@require_POST
def practice_exit(request, session_id):

    # Verify if the session belongs to the student
    session = _get_owned_session(request, session_id)

    # If the session has no associated micro-skill (admin removes the skill when students attempt), it is marked as an abandoned session
    if session.micro_skill is None:
        return _abandon_skill_less_session(session)

    # If the session is not completed, and the student has answered at least one question
    if not session.is_complete and session.answered_count:

        # Record the session details and update the mastery snapshot
        session.total_questions = session.answered_count
        session.current_question = None
        session.current_predicted_prob = None
        session.current_proximity = None
        _finalise_session(session)

    # Then redirect students back to the learning path page
    return redirect("learning:learning_path")


# A function to close out a practice session without a micro skill
def _abandon_skill_less_session(session):

    # If the session is not completed, save the current attempted questions
    if not session.is_complete:
        session.total_questions = session.answered_count or session.total_questions
        session.current_question = None
        session.current_predicted_prob = None
        session.current_proximity = None
        session.is_complete = True
        session.completed_at = timezone.now()
        session.save()

    # Then redirect students back to the learning path page
    return redirect("learning:learning_path")


# A function to record a mastery snapshot after completing a session
def _finalise_session(session):

    # Retrieve the mastery level for the skill
    mastery = services.get_mastery(session.student, session.micro_skill)

    # Update the session with corresponding details and save it to database
    session.mastery_after = mastery.bkt_mastery
    session.is_complete = True
    session.completed_at = timezone.now()
    session.save()
    MasterySnapshot.objects.create(
        student=session.student,
        overall_mastery=services.overall_mastery(session.student),
    )


# A function to render the result page after completing a quiz set
@login_required
def practice_results(request, session_id):

    # Verify if the session belongs to the student
    session = _get_owned_session(request, session_id)

    # If the session is not completed, redirect students back to the practice question page
    if not session.is_complete:
        return redirect("learning:practice_question", session_id=session.id)

    # Sort questions by the time they were attempted
    attempts = (
        session.attempts.select_related("question", "question__micro_skill")
        .order_by("created_at")
    )

    # Retrieve the details of each question
    review = []
    for a in attempts:
        review.append(
            {
                "attempt": a,
                "question": a.question,
                "correct_answer": a.question.correct_answer_display(),
            }
        )

    # Retrieve the current mastery level for the skill
    mastery = (
        services.get_mastery(session.student, session.micro_skill)
        if session.micro_skill
        else None
    )

    # Determine the mastery level after the session
    ending = session.mastery_after
    if ending is None:
        ending = mastery.bkt_mastery if mastery else 0.0
    mastery_percent = bkt.to_percent(ending)
    level_slug = services.mastery_level_slug(ending)

    # Determine the mastery level before the session
    mastery_before_percent = (
        bkt.to_percent(session.mastery_before)
        if session.mastery_before is not None
        else None
    )

    # Calculate the difference in mastery before and after session
    mastery_delta = (
        mastery_percent - mastery_before_percent
        if mastery_before_percent is not None
        else None
    )

    # Compile all details
    context = {
        "session": session,
        "review": review,
        "mastery": mastery,
        "mastery_percent": mastery_percent,
        "mastery_level_slug": level_slug,
        "mastery_before_percent": mastery_before_percent,
        "mastery_delta": mastery_delta,
        "mastery_delta_abs": abs(mastery_delta) if mastery_delta is not None else None,
        "mastery_label": services.LEVEL_LABELS[level_slug] if session.attempts.exists() else "Not started",
    }

    # If it is an AJAX request (activity page)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "student/_practice_results_content.html", context)

    # If it is a browser request (practice results page)
    return render(request, "student/practice_results.html", context)


# A function to verify that the practice session belongs to the student
def _get_owned_session(request, session_id):

    # Check if the session ID is valid
    session = get_object_or_404(
        PracticeSession.objects.select_related("micro_skill"), id=session_id
    )

    # Check if the current user is the same as the student associated with the session
    if session.student_id != request.user.id:
        raise Http404

    # Return session if everything looks good
    return session


# A function to retrieve the previous incompleted attempts on their diagnostic session
def _open_diagnostic(student):
    return (
        PracticeSession.objects.filter(
            student=student, kind=PracticeSession.Kind.DIAGNOSTIC, is_complete=False
        )
        .order_by("-created_at")
        .first()
    )


# A function to render the welcome screen for the diagnostic session
@login_required
def diagnostic_intro(request):

    # Redirect teachers to their dashboard
    if request.user.is_teacher:
        return redirect("classes:teacher_dashboard")

    # If the student already completed the diagnostic, redirect to the dashboard
    if not services.get_profile(request.user).needs_diagnostic:
        return redirect("learning:dashboard")

    # Check if there is a diagnostic session in progress for the student
    in_progress = _open_diagnostic(request.user)

    # Compile the context and render the diagnostic introduction page
    context = {
        "total": in_progress.total_questions
        if in_progress
        else diagnostic.planned_length(request.user),
        "in_progress": in_progress,
        "answered": in_progress.attempts.count() if in_progress else 0,
    }
    return render(request, "student/diagnostic_intro.html", context)


# A function to start a new diagnostic session
@login_required
def diagnostic_start(request):

    # Redirect teachers to their dashboard
    if request.user.is_teacher:
        return redirect("classes:teacher_dashboard")

    # If the student already completed the diagnostic, redirect to the dashboard
    if not services.get_profile(request.user).needs_diagnostic:
        return redirect("learning:dashboard")

    # Check if there is a diagnostic session in progress for the student
    session = _open_diagnostic(request.user)

    # For new diagnostic sessions
    if session is None:

        # Determien the number of diagnostic questions for the student
        total = diagnostic.planned_length(request.user)

        # If there are no questions available (empty question bank), mark it as complete and redirect to dashboard
        if not total:
            services.mark_diagnostic_complete(request.user)
            messages.info(
                request,
                "No diagnostic questions are available yet — starting you on the standard path.",
            )
            return redirect("learning:dashboard")

        # Create a new diagnostic session for the student
        session = PracticeSession.objects.create(
            student=request.user,
            micro_skill=None,
            kind=PracticeSession.Kind.DIAGNOSTIC,
            total_questions=total,
        )

    # Redirect students to the diagnostic questions page
    return redirect("learning:diagnostic_question", session_id=session.id)


# A function to show the current diagnostic question
@login_required
def diagnostic_question(request, session_id):

    # Verify if the session belongs to the student
    session = _get_owned_session(request, session_id)

    # If the session is not a diagnostic session, raise a 404 error
    if session.kind != PracticeSession.Kind.DIAGNOSTIC:
        raise Http404

    # If the session is already completed, redirect to the diagnostic results page
    if session.is_complete:
        return redirect("learning:diagnostic_results", session_id=session.id)

    # If the student submits an answer
    if request.method == "POST" and session.current_question is not None:

        # Record the current attempt
        _, is_correct = services.record_attempt(
            request.user,
            session.current_question,
            request.POST.get("answer", ""),
            session=session,
            predicted_prob=session.current_predicted_prob,
            response_time_sec=_response_time(request),
        )

        # Update score, reset the current question, and save the attempt
        if is_correct:
            session.score += 1
        session.current_question = None
        session.current_predicted_prob = None
        session.save(
            update_fields=[
                "score",
                "current_question",
                "current_predicted_prob",
            ]
        )

        # Redirect to the next question
        return redirect("learning:diagnostic_question", session_id=session.id)

    # If the session does not have a question currently
    if session.current_question is None:

        # Let the diagnostic recommender choose the next question
        question = diagnostic.next_question(session)

        # End the session if there are no more questions available
        if question is None:
            return _finish_diagnostic(session)

        # Update the session with the chosen question and save into database
        prob = recommender.predict_correct_prob(request.user, question)
        session.current_question = question
        session.current_predicted_prob = prob
        session.save(
            update_fields=["current_question", "current_predicted_prob"]
        )

    # Determine the number of questions answered in this diagnostic session
    answered = session.answered_count

    # Compile the context and render the diagnostic page
    context = {
        "session": session,
        "question": session.current_question,
        "answer_choices": session.current_question.choices_in_display_order(session.id),
        "question_number": answered + 1,
        "total": session.total_questions,
        "progress_percent": round(answered / session.total_questions * 100)
        if session.total_questions
        else 0,
    }
    return render(request, "student/diagnostic.html", context)


# A function to end the diagnostic test
def _finish_diagnostic(session):

    # Mark the diagnostic session as complete
    session.total_questions = session.answered_count or session.total_questions
    session.current_question = None
    session.is_complete = True
    session.completed_at = timezone.now()
    session.save()
    services.mark_diagnostic_complete(session.student, when=session.completed_at)

    # Record a mastery snapshot for the student
    MasterySnapshot.objects.create(
        student=session.student,
        overall_mastery=services.overall_mastery(session.student),
    )

    # Redirect students to the diagnostic results page
    return redirect("learning:diagnostic_results", session_id=session.id)


# A function to render the diagnostic results page
@login_required
def diagnostic_results(request, session_id):

    # Verify if the session belongs to the student
    session = _get_owned_session(request, session_id)

    # If the session is not a diagnostic session, raise a 404 error
    if session.kind != PracticeSession.Kind.DIAGNOSTIC:
        raise Http404

    # If the session is not completed, redirect students back to the diagnostic question page
    if not session.is_complete:
        return redirect("learning:diagnostic_question", session_id=session.id)

    # Retrieve the recommended starting skill
    rec_skill = diagnostic.recommend_starting_skill(request.user)

    # Generate the micro skill report for the student
    topics = diagnostic.micro_skill_report(
        request.user, session, recommended_skill=rec_skill
    )

    # Compile the context and render the diagnostic results page
    context = {
        "session": session,
        "topics": topics,
        "rec_skill": rec_skill,
    }
    return render(request, "student/diagnostic_results.html", context)


# A function to retrieve the time spent on answering a question
def _response_time(request):

    # Retrieve the response time from the POST data
    raw = request.POST.get("response_time_sec") or None

    # Convert the time to a float
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


# A function to render the student activity history page
@login_required
def activity(request):

    # Redirect teachers to their dashboard
    if request.user.is_teacher:
        return redirect("classes:teacher_dashboard")

    # Extract the student object
    student = request.user

    # Extract the filter applied on the page
    domain_filter = request.GET.get("domain", "")
    tier_filter = request.GET.get("tier", "")
    when_filter = request.GET.get("when", "")

    # Retrieve the number of records to show
    try:
        show = max(ACTIVITY_INITIAL, int(request.GET.get("show", ACTIVITY_INITIAL)))
    except ValueError:
        show = ACTIVITY_INITIAL

    # Retrieve all practice sessions for the student
    qs = (
        PracticeSession.objects.filter(student=student, is_complete=True)
        .exclude(kind=PracticeSession.Kind.DIAGNOSTIC)
        .select_related("micro_skill", "micro_skill__macro_domain")
        .annotate(
            ratio=ExpressionWrapper(
                1.0 * F("score") / F("total_questions"), output_field=FloatField()
            )
        )
    )

    # Apply the filters if necessary
    # Filter on domains
    if domain_filter.isdigit():
        qs = qs.filter(micro_skill__macro_domain_id=domain_filter)
    else:
        domain_filter = ""

    # Filter on mastery tiers
    if tier_filter == "strong":
        qs = qs.filter(ratio__gte=SCORE_TIER_STRONG)
    elif tier_filter == "weak":
        qs = qs.filter(ratio__lt=SCORE_TIER_WEAK)
    elif tier_filter == "moderate":
        qs = qs.filter(ratio__gte=SCORE_TIER_WEAK, ratio__lt=SCORE_TIER_STRONG)

    # Filter on time periods
    now = timezone.localtime(timezone.now())
    if when_filter == "today":
        qs = qs.filter(completed_at__gte=now.replace(hour=0, minute=0, second=0, microsecond=0))
    elif when_filter == "week":
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(completed_at__gte=start)
    elif when_filter == "month":
        qs = qs.filter(completed_at__gte=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))

    # Sort the sessions by completion time
    qs = qs.order_by("-completed_at")

    # Calculate the statistics and compile the context
    total = qs.count()
    sessions = [{"session": s, "tier": _score_tier(s)} for s in qs[:show]]
    context = {
        "sessions": sessions,
        "has_more": total > show,
        "load_more_url": _activity_url(request, show=show + ACTIVITY_INCREMENT),
        "when_options": [
            {"label": "All time", "url": _activity_url(request, when="", show=""), "active": when_filter == ""},
            {"label": "Today", "url": _activity_url(request, when="today", show=""), "active": when_filter == "today"},
            {"label": "This week", "url": _activity_url(request, when="week", show=""), "active": when_filter == "week"},
            {"label": "This month", "url": _activity_url(request, when="month", show=""), "active": when_filter == "month"},
        ],
        "domain_options": [
            {"label": "All topics", "url": _activity_url(request, domain="", show=""), "active": domain_filter == ""},
        ]
        + [
            {
                "label": d.name,
                "url": _activity_url(request, domain=str(d.id), show=""),
                "active": domain_filter == str(d.id),
            }
            for d in MacroDomain.objects.order_by("order")
        ],
        "tier_options": [
            {"label": "All scores", "url": _activity_url(request, tier="", show=""), "active": tier_filter == ""},
            {"label": "Strong (80%+)", "url": _activity_url(request, tier="strong", show=""), "active": tier_filter == "strong"},
            {"label": "Moderate", "url": _activity_url(request, tier="moderate", show=""), "active": tier_filter == "moderate"},
            {"label": "Weak (under 40%)", "url": _activity_url(request, tier="weak", show=""), "active": tier_filter == "weak"},
        ],
        "when_filter_active": bool(when_filter),
        "domain_filter_active": bool(domain_filter),
        "tier_filter_active": bool(tier_filter),
        "any_filter_active": bool(domain_filter or tier_filter or when_filter),
        "has_history": PracticeSession.objects.filter(
            student=student, is_complete=True
        ).exclude(kind=PracticeSession.Kind.DIAGNOSTIC).exists(),
    }

    # Lastly, render the activity page with the compiled context
    return render(request, "student/activity.html", context)


# A function to load the activity page without losing filter
def _activity_url(request, **overrides):

    # Retrieve the current parameters for GET requests
    params = request.GET.copy()

    # Override current parameters with valid values
    for key, value in overrides.items():
        if value:
            params[key] = str(value)
        else:
            params.pop(key, None)

    # Encode the parameters into a query string and return the URL
    qs = params.urlencode()
    return f"?{qs}" if qs else "."


# A function to assign a tier to practice sessions
def _score_tier(session):

    # If there are no questions answered, assign a moderate tier
    if not session.total_questions:
        return "moderate"

    # Calculate the ratio
    ratio = session.score / session.total_questions

    # Strong if the ratio is above the strong threshold
    if ratio >= SCORE_TIER_STRONG:
        return "strong"

    # Weak if the ratio is below the weak threshold
    if ratio < SCORE_TIER_WEAK:
        return "weak"

    # Moderate otherwise
    return "moderate"
