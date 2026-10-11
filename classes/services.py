"""
This file contains the logic to calculate student statistics on the teachers' side.
"""

import math
from datetime import datetime, time, timedelta

from django.conf import settings
from django.utils import timezone

from ml_engine import bkt
from ml_engine import services as ml_services

# 80% is considered mastered, 50% is considered just hit the minimum mastery
MASTERY_PERCENT = round(settings.MASTERY_THRESHOLD * 100)
SUPPORT_THRESHOLD = round(settings.MASTERY_DEVELOPING * 100)

# The color used for the mastery ring
_MASTERY_TIER_COLORS = {
    "weak": "#e56d2f",
    "mid": "#a6780c",
    "mastered": "#3f665c",
}

# A function to build the summary of a student
def student_overview(student):
    from learning.models import Attempt, SkillMastery

    # Retrieve the list of skills of the student
    masteries = list(
        SkillMastery.objects.filter(student=student, attempts__gt=0).select_related(
            "micro_skill"
        )
    )

    # The BKT mastery in overall
    overall = bkt.to_percent(ml_services.overall_mastery(student))

    # The most recent attempts of students
    last_attempt = (
        Attempt.objects.filter(student=student).order_by("-created_at").first()
    )

    # Weakest skill = lowest BKT mastery, Strongest skill = highest BKT mastery
    weakest = min(masteries, key=lambda m: m.bkt_mastery, default=None)
    strongest = max(masteries, key=lambda m: m.bkt_mastery, default=None)

    # Once finish calculation, return all details
    return {
        "student": student,
        "overall": overall,
        "last_active": last_attempt.created_at if last_attempt else None,
        "weakest": weakest.micro_skill if weakest else None,
        "strongest": strongest.micro_skill if strongest else None,
        "attempted": len(masteries),
    }


# A function to return the start of the current calendar week (Monday)
def current_week_start():
    today = timezone.localdate()
    return timezone.make_aware(
        datetime.combine(today - timedelta(days=today.weekday()), time.min)
    )


# A function to list the students inside a class
def class_members(school_class):
    return [m.student for m in school_class.active_memberships.select_related("student")]


# A function to calculate the summary data for a class
def class_summary(school_class):

    # Retrieve the list of students in a class
    members = class_members(school_class)

    # Calculate the summary for each student
    overviews = [student_overview(s) for s in members]

    # Class mastery = Average of student mastery
    avg = round(sum(o["overall"] for o in overviews) / len(overviews)) if overviews else 0

    # Calculate the students who are active this week (Monday onwards, matching the weekly engagement modal)
    week_start = current_week_start()
    active_week = sum(1 for o in overviews if o["last_active"] and o["last_active"] >= week_start)

    # Retrieve the weakest skill in the class
    weakest_skill = weakest_skills_for(members, limit=1)

    # Return the outputs after extracted
    return {
        "class": school_class,
        "student_count": len(members),
        "avg_mastery": avg,
        "active_week": active_week,
        "weakest_skill": weakest_skill[0]["skill"] if weakest_skill else None,
        "overviews": overviews,
    }


# A function to categorize mastery percentage into tiers
def mastery_tier(percent):

    # Above the mastery percentage means its mastered
    if percent >= MASTERY_PERCENT:
        return "mastered"

    # Above the support threshold means its progressing
    if percent >= SUPPORT_THRESHOLD:
        return "mid"

    # Below means the student did not master
    return "weak"


# A function to determine the color for the mastery donut ring
def mastery_ring_color(percent):
    return _MASTERY_TIER_COLORS[mastery_tier(percent)]


# A function to calculate the number of active students and create a sparkline chart for past 5 days (in default)
def weekly_engagement(students, days=5):
    from learning.models import Attempt

    # Retrieve the number of students who attempted for the past few days
    today = timezone.localdate()
    day_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    counts = [
        Attempt.objects.filter(student__in=students, created_at__date=d)
        .order_by().values("student").distinct().count()
        if students else 0
        for d in day_list
    ]

    # Create the sparkline box
    width, height, pad_y = 280, 50, 6

    # Retrieve the statistics: number of students attempted and its maximum
    peak = max(counts) or 1
    n = len(counts)

    # Plot the chart
    points = []
    for i, (day, count) in enumerate(zip(day_list, counts)):
        x = round(i * width / (n - 1), 1) if n > 1 else width / 2
        y = round(height - pad_y - (count / peak) * (height - 2 * pad_y), 1)
        points.append({"label": day.strftime("%a"), "count": count, "x": x, "y": y})

    # Lastly, return the statistics and the sparkline chart
    return {
        "points": points,
        "polyline": " ".join(f"{p['x']},{p['y']}" for p in points),
        "active_today": counts[-1],
        "width": width,
        "height": height,
    }


# A function to retrieve the student active for the current week
def weekly_engagement_by_weekday(students):
    from learning.models import Attempt

    # Extract today's date and Monday, as well as student ID
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    by_id = {s.id: s for s in students}

    # Loop through each day
    days = []
    for i in range(7):
        day = monday + timedelta(days=i)

        # Extract the list of student IDs who are active on that dat
        student_ids = (
            Attempt.objects.filter(student__in=students, created_at__date=day)
            .order_by().values_list("student_id", flat=True).distinct()
            if students else []
        )

        # Sort the students by name and add to list
        day_students = sorted((by_id[sid] for sid in student_ids), key=lambda s: s.full_name)
        days.append({
            "label": day.strftime("%A"),
            "date": day,
            "students": day_students,
            "count": len(day_students),
            "is_today": day == today,
            "is_future": day > today,
            "share": round(100 * len(day_students) / len(by_id)) if by_id else 0,
        })

    # Return list of students
    return days


# A function to format a week range (e.g. 7 - 13 September)
def week_range_label(days):

    # Return empty string if no days are provided
    if not days:
        return ""

    # Retrieve the start and end date
    start, end = days[0]["date"], days[-1]["date"]

    # Only show month once if month is the same
    if start.month == end.month:
        return f"{start.day} – {end.day} {end.strftime('%B')}"

    # If not, show both day and months
    return f"{start.day} {start.strftime('%B')} – {end.day} {end.strftime('%B')}"


# A function to find the worst performing skills of a student
def weakest_skills_for(students, limit=5):
    from learning.models import SkillMastery

    # Return empty if students are not provided
    if not students:
        return []

    # Each skill is mapped to a list of student masteries
    buckets = {}
    qs = SkillMastery.objects.filter(
        student__in=students, attempts__gt=0
    ).select_related("micro_skill")
    for m in qs:
        buckets.setdefault(m.micro_skill, []).append(m.bkt_mastery)

    # Average student mastery and sort them ascendingly
    rows = []
    for skill, v in buckets.items():
        avg = bkt.to_percent(sum(v) / len(v))
        rows.append({"skill": skill, "avg": avg, "students": len(v), "tier": mastery_tier(avg)})
    rows.sort(key=lambda r: r["avg"])

    # Retrieve the first N number of skills
    return rows[:limit]


# A function to group skills under their macro domains
def weakest_skills_by_topic(students):

    # Retrieve the list of weakest skills
    rows = weakest_skills_for(students, limit=None)

    # Retrieve the macro domain for each skill
    topics = {}
    for row in rows:
        topics.setdefault(row["skill"].macro_domain, []).append(row)

    # Calculate the average for each macro domain and sort it
    grouped = []
    for domain, skills in topics.items():
        avg = round(sum(s["avg"] for s in skills) / len(skills))
        grouped.append(
            {
                "domain": domain,
                "skills": skills,
                "avg": avg,
                "color": mastery_ring_color(avg),
            }
        )
    grouped.sort(key=lambda g: g["avg"])

    # Lastly, return the list of macro domains with their averaged mastery
    return grouped


# A function to retrieve students with overall mastery level below the support threshold
def students_needing_attention(students, limit=6):

    # Retrieve students below support threshold
    rows = [o for o in (student_overview(s) for s in students)
            if o["attempted"] and o["overall"] < SUPPORT_THRESHOLD]

    # Sort the students based on overall mastery level and return them
    rows.sort(key=lambda r: r["overall"])
    return rows[:limit]


# A function to group the students who are below support threshold by class
def attention_by_class(rows):

    # Retrieve the classes with list of struggling students
    classes = {}
    for row in rows:
        classes.setdefault(row.get("class_name") or "Unassigned", []).append(row)

    # Calculate the average mastery of struggling students
    grouped = []
    for class_name, students in classes.items():
        avg = round(sum(s["overall"] for s in students) / len(students))
        grouped.append(
            {
                "class_name": class_name,
                "students": students,
                "avg": avg,
                "color": mastery_ring_color(avg),
            }
        )

    # Sort them in ascending order based on average mastery level
    grouped.sort(key=lambda g: g["avg"])
    return grouped


# A function to group students in a class into their mastery tiers
def mastery_distribution_groups(overviews):

    # Define the different tiers
    bands = [
        ("Needs support", "#e56d2f", "weak"),
        ("In progress", "#a6780c", "mid"),
        ("Mastered", "#3f665c", "mastered"),
    ]

    # Calculate the total number of students
    total = len(overviews)

    # Group students into their tiers
    groups = []
    for label, color, tier in bands:
        members = sorted(
            (o for o in overviews if mastery_tier(o["overall"]) == tier),
            key=lambda o: o["overall"],
        )
        groups.append({
            "label": label,
            "color": color,
            "students": members,
            "count": len(members),
            "pct": round(len(members) / total * 100) if total else 0,
        })

    # Lastly, return the groups
    return groups


# A function to convert different mastery tiers into donut chart
def distribution_donut_arcs(groups, radius=40):

    # Calculate the circumference of the chart
    circumference = 2 * math.pi * radius

    # Calculate the total number of students
    total = sum(g["count"] for g in groups)

    # Begin from degree 0
    cursor = 0.0

    # Calculate the size of arc, then record the information
    arcs = []
    for g in groups:
        length = circumference * (g["count"] / total) if total else 0
        arcs.append({
            **g,
            "dasharray": f"{length:.3f} {circumference - length:.3f}",
            "dashoffset": f"{-cursor:.3f}",
        })
        cursor += length

    # Return the information to be used in the chart
    return arcs
