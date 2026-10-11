"""
This file handles the request routed from URLs to render HTML for the classes directory.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from curriculum import graph
from curriculum.models import MicroSkill
from learning.models import Attempt, SkillMastery
from ml_engine import bkt
from ml_engine import services as ml_services

from . import services
from .forms import AddStudentForm, CreateClassForm
from .models import Membership, SchoolClass, TopicAvailability


# The number of items to be shown in a panel
DASHBOARD_LIST_LIMIT = 2
CLASS_LIST_LIMIT = 3

# The threshold that indicates students have achieved minimum proficiency
SUPPORT_THRESHOLD = services.SUPPORT_THRESHOLD


# A function to enable and disable teacher's restriction on hidden topics
@login_required
@require_POST
def toggle_restrictions(request, class_id):

    # First, check if the student has a class and is active
    membership = get_object_or_404(
        Membership, school_class_id=class_id, student=request.user, is_active=True
    )

    # Switch the state of restriction and save it
    membership.restrictions_disabled = not membership.restrictions_disabled
    membership.save(update_fields=["restrictions_disabled"])

    # Generate the corresponding notifications
    if membership.restrictions_disabled:
        messages.success(request, "All topics are now visible.")
    else:
        messages.success(request, "Teacher restrictions applied.")

    # Redirect back to the profile page
    return redirect("accounts:profile")


# A function to deny permission to access teacher's page for non-authentication users
def _teacher_required(request):

    # Raise exceptions if the user is unauthenticated or if the user is not a teacher
    if not request.user.is_authenticated or not request.user.is_teacher:
        raise PermissionDenied


# A function to retrieve the class of a teacher
def _owned_class(request, class_id):

    # First, check if the class exist
    school_class = get_object_or_404(SchoolClass, id=class_id)

    # Raise exceptions if the teacher ID of the class does not match user
    if school_class.teacher_id != request.user.id:
        raise PermissionDenied

    # Return the class object
    return school_class


# A function to render teacher's main dashboard (main page)
@login_required
def teacher_dashboard(request):

    # If the user is a student, redirect to their main page
    if request.user.is_student:
        return redirect("learning:dashboard")

    # Retrieve teacher and class information
    teacher = request.user
    classes = list(teacher.classes_taught.filter(is_active=True))
    summaries = [services.class_summary(c) for c in classes]

    # Retrieve all students, as well as the mapping of each student to their class
    all_students = []
    class_by_student = {}
    for c in classes:
        members = services.class_members(c)
        all_students.extend(members)
        for s in members:
            class_by_student.setdefault(s.id, c.name)
    unique_students = list({s.id: s for s in all_students}.values())

    # Retrieve the number of students who are active in the current week
    week_start = services.current_week_start()
    active_week = (
        Attempt.objects.filter(student__in=unique_students, created_at__gte=week_start)
        .values("student")
        .distinct()
        .count()
    )

    # Extract the weakest micro skill and macro domain
    weakest_skills = services.weakest_skills_for(unique_students, limit=None)
    weakest_topics = services.weakest_skills_by_topic(unique_students)

    # Extract the students who require attention (below support threshold)
    attention = services.students_needing_attention(unique_students, limit=None)

    # Group the students requiring attention by their class
    for row in attention:
        row["class_name"] = class_by_student.get(row["student"].id, "")
    attention_groups = services.attention_by_class(attention)

    # Extract the first N students requiring attention (for students needing attention card)
    attention_preview = attention[:DASHBOARD_LIST_LIMIT]
    if attention_preview:
        attention_preview = attention_preview + [None] * (
            DASHBOARD_LIST_LIMIT - len(attention_preview)
        )

    # Compile the data collected
    context = {
        "summaries": summaries,
        "class_count": len(classes),
        "student_count": len(unique_students),
        "active_week": active_week,
        "weakest_skills": weakest_skills,
        "weakest_topics": weakest_topics,
        "support_count": sum(1 for w in weakest_skills if w["avg"] < SUPPORT_THRESHOLD),
        "attention": attention,
        "attention_groups": attention_groups,
        "attention_preview": attention_preview,
        "dashboard_list_limit": DASHBOARD_LIST_LIMIT,
        "dashboard_slice": f":{DASHBOARD_LIST_LIMIT}",
        "class_slice": f":{CLASS_LIST_LIMIT}",
    }

    # Pass the data into the dashboard HTML
    return render(request, "teacher/dashboard.html", context)


# A function to extract the information required by the class card at "My Classes" tab
def _class_summaries(teacher):

    # Extract details of each class
    summaries = []
    for school_class in teacher.classes_taught.filter(is_active=True):

        # First, extract all information
        summary = services.class_summary(school_class)

        # Then only retain a few: Student requiring attention and average mastery
        members = [o["student"] for o in summary["overviews"]]
        summary["support_count"] = len(
            services.students_needing_attention(members, limit=None)
        )
        summary["mastery_tier"] = services.mastery_tier(summary["avg_mastery"])

        # And add to the summary list
        summaries.append(summary)

    # Return the list
    return summaries


# A function to render the cards for the "My Classes" tab
@login_required
def teacher_classes(request):

    # Check permission first
    _teacher_required(request)

    # Extract details
    context = {
        "summaries": _class_summaries(request.user),
        "create_form": CreateClassForm(),
    }

    # Pass details into HTML
    return render(request, "teacher/classes.html", context)


# A function to handle the form to create new classes
@login_required
@require_POST
def create_class(request):

    # Permission check
    _teacher_required(request)

    # Check if the input is valid
    form = CreateClassForm(request.POST)
    if form.is_valid():

        # Create the class and save to database
        school_class = form.save(commit=False)
        school_class.teacher = request.user
        school_class.save()

        # Generate successful notification and redirect to the class dashboard
        messages.success(
            request,
            f"Class '{school_class.name}' created. Add students from the Students tab.",
        )
        return redirect("classes:class_detail", class_id=school_class.id)

    # If input is invalid, re-render the form with errors
    context = {"summaries": _class_summaries(request.user), "create_form": form}
    return render(request, "teacher/classes.html", context)


# A function to delete a class and unenroll students
@login_required
@require_POST
def delete_class(request, class_id):

    # Check permission first
    _teacher_required(request)

    # Extract relevant class details
    school_class = _owned_class(request, class_id)
    name = school_class.name
    removed = school_class.active_memberships.count()

    # Perform deletion
    school_class.delete()

    # Check if any students are unenrolled and generate the corresponding message
    if removed:
        messages.success(
            request,
            f"Deleted {name} and unenrolled "
            f"{removed} student{'' if removed == 1 else 's'}.",
        )
    else:
        messages.success(request, f"Deleted {name}.")

    # Once done, redirect to the "My Classes" tab
    return redirect("classes:teacher_classes")


# A function to render the detail page of a class
@login_required
def class_detail(request, class_id):

    # Check for permission
    _teacher_required(request)
    school_class = _owned_class(request, class_id)

    # Make the default landing page to be the overview tab
    tab = request.GET.get("tab", "overview")
    if tab not in ("overview", "students", "availability"):
        tab = "overview"

    # Extract the details of each student in the class
    members = services.class_members(school_class)
    overviews = [services.student_overview(s) for s in members]
    overviews.sort(key=lambda o: o["overall"])

    # Count the number of active students for the week
    week_start = services.current_week_start()
    active_week = sum(1 for o in overviews if o["last_active"] and o["last_active"] >= week_start)

    # Compile the overall data into JSON format
    context = {
        "school_class": school_class,
        "tab": tab,
        "student_count": len(members),
        "overviews": overviews,
        "avg_mastery": round(sum(o["overall"] for o in overviews) / len(overviews)) if overviews else 0,
        "active_week": active_week,
    }

    # If the current selected tab is overview, extract the class summary information
    if tab == "overview":
        context["weakest_skills"] = services.weakest_skills_for(members, limit=2)
        context["weakest_topics"] = services.weakest_skills_by_topic(members)
        context["weekly_engagement"] = services.weekly_engagement(members)
        week = services.weekly_engagement_by_weekday(members)
        context["weekly_engagement_week"] = week
        context["weekly_engagement_range"] = services.week_range_label(week)
        distribution_groups = services.mastery_distribution_groups(overviews)
        context["distribution_groups"] = services.distribution_donut_arcs(distribution_groups)
        context["recent_attempts"] = (
            Attempt.objects.filter(student__in=members)
            .select_related("student", "question", "micro_skill", "session")
            .order_by("-created_at")[:10]
        )

    # If the current selected tab is topic availability (page to hide skills)
    elif tab == "availability":
        context.update(_roadmap(school_class, request.GET.get("view") == "preview"))

    # If the current selected tab is student list
    elif tab == "students":

        # Clear invalid emails
        rejected = request.session.pop("add_student_rejected", None)

        # If there is nothing to clear, show the email input form
        if rejected is None:
            context["add_student_form"] = AddStudentForm()

        # If not, show the error message
        else:
            form = AddStudentForm({"email": rejected})
            form.is_valid()
            context["add_student_form"] = form

    # Pass the data into the HTML template and render it
    return render(request, "teacher/class_detail.html", context)


# A function to redirect teachers to "Students" tab
def _students_tab(school_class):
    return f"{reverse('classes:class_detail', args=[school_class.id])}?tab=students"


# A function to enroll a student into class
@login_required
@require_POST
def add_student(request, class_id):

    # Check permission
    _teacher_required(request)
    school_class = _owned_class(request, class_id)

    # Attach the field from the form
    form = AddStudentForm(request.POST)

    # If the input iw wrong, add error message
    if not form.is_valid():
        request.session["add_student_rejected"] = request.POST.get("email", "")
        return redirect(_students_tab(school_class))

    from accounts.models import User

    # Else, if input is correct, clean the email and check if it maps to a student
    email = form.cleaned_data["email"]
    student = User.objects.filter(email=email, role=User.Role.STUDENT).first()
    if not student:
        messages.error(request, f"No student account found for {email}.")
        return redirect(_students_tab(school_class))

    # If yes, then check if the student is already in another class
    existing = (
        Membership.objects.filter(student=student, is_active=True)
        .exclude(school_class=school_class)
        .select_related("school_class", "school_class__teacher")
        .first()
    )

    # If student is already in a class, show error
    if existing:
        messages.error(
            request,
            f"{student.full_name} is already in {existing.school_class.name} "
            f"(teacher: {existing.school_class.teacher.full_name}). "
            "That teacher must remove them before you can add them here.",
        )
        return redirect(_students_tab(school_class))

    # if all validation passed, create the membership and add student to class
    membership, created = Membership.objects.get_or_create(
        school_class=school_class, student=student
    )

    # Show error if the student is already added to this class
    if not created and membership.is_active:
        messages.info(request, f"{student.full_name} is already in this class.")

    # If everything is fine, update to the database and show successful
    else:
        membership.is_active = True
        membership.restrictions_disabled = False
        membership.save(update_fields=["is_active", "restrictions_disabled"])
        messages.success(request, f"Added {student.full_name} to {school_class.name}.")

    # Once done, redirect the page to the current opening tab
    return redirect(_students_tab(school_class))


# A function to remove a student from a class
@login_required
@require_POST
def remove_student(request, class_id, student_id):

    # Check for permission
    _teacher_required(request)
    school_class = _owned_class(request, class_id)

    # Check if the student is in the class
    membership = get_object_or_404(
        Membership, school_class=school_class, student_id=student_id, is_active=True
    )

    # If yes, change the student to inactive (to retain the learning records)
    name = membership.student.full_name
    membership.is_active = False
    membership.save(update_fields=["is_active"])
    messages.success(request, f"Removed {name} from {school_class.name}.")

    # Lastly, redirect the page to the students tab
    return redirect(_students_tab(school_class))


# A function to build the roadmap to show and hide chapters
def _roadmap_rows(school_class):

    # Retrieve the list of skills hidden by teachers
    hidden_ids = set(
        school_class.topic_settings.filter(is_available=False).values_list(
            "micro_skill_id", flat=True
        )
    )

    # Retrieve the list of all skills
    skills = (
        MicroSkill.objects.filter(is_active=True)
        .select_related("macro_domain")
        .prefetch_related("prerequisites")
        .order_by("form_level", "order")
    )

    # Retrieve the status of each skill
    rows = [{"skill": s, "included": s.id not in hidden_ids} for s in skills]

    # Map each skill ID to its skill
    by_id = {r["skill"].id: r for r in rows}

    # Loop through each skill ordered with prerequisite
    for row in graph.in_prerequisite_order(rows):

        # Retrieve the skill's prerequisite
        prereqs = [by_id[p.id] for p in row["skill"].prerequisites.all() if p.id in by_id]

        # Check if the skill is reachable
        row["reachable"] = row["included"] and all(p["reachable"] for p in prereqs)

        # Determine the status: Teacher turned off the skill
        if not row["included"]:
            row["state"] = "excluded"

        # Skill is turned on and reachable
        elif row["reachable"]:
            row["state"] = "included"

        # Skill is turned on but not reachable
        else:
            row["state"] = "unreachable"

    # Return the list of skills with their status
    return rows


# A function to build the skill roadmap for the class
def _roadmap(school_class, preview):

    # Extract the list of skills and their status
    rows = _roadmap_rows(school_class)

    # Mapping to facilitate lookup later
    by_id = {r["skill"].id: r for r in rows}
    by_slug = {r["skill"].slug: r for r in rows}

    # Depending on the mode, either show or hide skills turned off by teacher
    shown = [r for r in rows if r["included"]] if preview else rows

    # Build the skill roadmap graph
    diagram = graph.build_graph(shown)

    # Loop through each edge
    for edge in diagram["edges"]:

        # Check the target and source of the edge
        target = by_slug.get(edge["target"])
        source = by_slug.get(edge["source"])

        # Determine if the skill is reachable or not: severed means unreachable, live means reachable
        edge["severed"] = bool(target and source and target["included"] and not source["reachable"])
        edge["live"] = bool(target and source and target["reachable"] and source["reachable"])

    # Once done, return the details to draw the graph
    return {
        "roadmap": diagram,
        "roadmap_preview": preview,
        "roadmap_total": len(rows),
        "roadmap_included": sum(1 for r in rows if r["included"]),
        "roadmap_unreachable": sum(1 for r in rows if r["state"] == "unreachable"),
        "roadmap_prereqs": json.dumps(
            {
                r["skill"].slug: [
                    p.slug for p in r["skill"].prerequisites.all() if p.id in by_id
                ]
                for r in rows
            }
        ),
    }


# A function for teachers to switch the topic on or off
@login_required
@require_POST
def toggle_topic(request, class_id):

    # Check for permissions
    _teacher_required(request)
    school_class = _owned_class(request, class_id)

    # Retrieve the skill ID who invoked the request and check if it exists
    skill_id = request.POST.get("skill_id")
    skill = get_object_or_404(MicroSkill, id=skill_id)

    # Determine if the skill is to be made available or not
    make_available = request.POST.get("available") == "true"

    # Create the record for topic availability, update it, and save to database
    setting, _ = TopicAvailability.objects.get_or_create(
        school_class=school_class, micro_skill=skill
    )
    setting.is_available = make_available
    setting.save(update_fields=["is_available"])

    # Lastly, return the JSON response to sync to browser
    return JsonResponse({"ok": True, "skill_id": skill.id, "available": make_available})


# A function to render individual student detail page
@login_required
def student_detail(request, class_id, student_id):

    # Check for permission
    _teacher_required(request)
    school_class = _owned_class(request, class_id)

    # Return error if the student is not in the class
    membership = get_object_or_404(
        Membership, school_class=school_class, student_id=student_id, is_active=True
    )

    # Retrieve the student object
    student = membership.student

    # Retrieve the student's mastery and attempts
    masteries = list(
        SkillMastery.objects.filter(student=student, attempts__gt=0)
        .select_related("micro_skill")
        .order_by("bkt_mastery")
    )
    attempts = (
        Attempt.objects.filter(student=student)
        .select_related("question", "micro_skill", "session")
        .order_by("-created_at")[:40]
    )

    # Compile the data together
    context = {
        "school_class": school_class,
        "student": student,
        "membership": membership,
        "overall": bkt.to_percent(ml_services.overall_mastery(student)),
        "last_active": attempts[0].created_at if attempts else None,
        "masteries": masteries,
        "skill_bands": _skill_bands(masteries),
        "attempts": attempts,
    }

    # Pass the data into the HTML template and render it
    return render(request, "teacher/student_detail.html", context)


# The labels to be displayed in student details page
_SKILL_BAND_LABELS = [
    ("weak", "Needs support", f"Below {SUPPORT_THRESHOLD}%"),
    ("mid", "Developing", f"{SUPPORT_THRESHOLD}–{services.MASTERY_PERCENT - 1}%"),
    ("mastered", "Secure", f"{services.MASTERY_PERCENT}% and above"),
]


# A function to group mastery into three tiers
def _skill_bands(masteries):

    # Create the dict to store mastery later
    grouped = {key: [] for key, _, _ in _SKILL_BAND_LABELS}

    # Loop through each mastery, retrieve their tiers, and add to the dict
    for m in masteries:
        grouped[services.mastery_tier(m.mastery_percent)].append(m)

    # Retrieve the total number of mastery to calculate statistics
    total = len(masteries)

    # Build the details for each band
    bands = [
        {
            "key": key,
            "label": label,
            "hint": hint,
            "rows": grouped[key],
            "count": len(grouped[key]),
            "share": round(100 * len(grouped[key]) / total, 2) if total else 0,
            "open": False,
        }
        for key, label, hint in _SKILL_BAND_LABELS
    ]

    # Only open the first band and close the rest on default
    for band in bands:
        if band["count"]:
            band["open"] = True
            break

    # Return all bands
    return bands
