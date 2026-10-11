"""
The file that contains the logic for admins to train BKT based on student data in the current system.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from curriculum.models import MicroSkill
from ml_engine import bkt
from ml_engine.bkt import BKTParams

# Only allow BKT to be trained when there's at least 100 students training, and each student has at least attempted 5 times.
# By setting a high value, this ensures that sufficient data is captured for BKT.
DEFAULT_MIN_STUDENTS = 100
DEFAULT_MIN_ATTEMPTS = 5


# An inherited class to allow commands to be executed in terminal
class Command(BaseCommand):

    # The first message printed when calling help, before the help of list of arguments are generated
    # Command: python manage.py fit_bkt --help
    help = (
        "Re-fit each skill's BKT parameters from recorded attempts using pyBKT."
        "Reports by default; pass --apply to write."
    )


    # Define the different arguments that can be specified
    def add_arguments(self, parser):

        # Trigger: python manage.py fit_bkt --apply
        parser.add_argument(
            "--apply", action="store_true",
            help="Write the fitted parameters. Without this the command only reports.",
        )

        # Trigger: python manage.py fit_bkt --reset
        parser.add_argument(
            "--reset", action="store_true",
            help="Restore every skill to the pooled training prior and exit.",
        )

        # Trigger: python manage.py fit_bkt --min-students
        parser.add_argument(
            "--min-students", type=int, default=DEFAULT_MIN_STUDENTS,
            help=f"Qualifying students a skill needs before it is fitted "
                 f"(default {DEFAULT_MIN_STUDENTS}).",
        )

        # Trigger: python manage.py fit_bkt --min-attempts
        parser.add_argument(
            "--min-attempts", type=int, default=DEFAULT_MIN_ATTEMPTS,
            help=f"Attempts on the skill for a student to count towards that "
                 f"total (default {DEFAULT_MIN_ATTEMPTS}).",
        )

        # Trigger: python manage.py fit_bkt --skill
        parser.add_argument(
            "--skill", metavar="SLUG",
            help="Fit only this micro-skill.",
        )

        # Trigger: python manage.py fit_bkt --no-shrink
        parser.add_argument(
            "--no-shrink", action="store_true",
            help="Use the raw BKT fit instead of shrinking it towards the prior. "
                 "Shrinking is on by default and is what keeps a thin fit from "
                 "replacing known-good values outright.",
        )

        # Trigger: python manage.py fit_bkt --force
        parser.add_argument(
            "--force", action="store_true",
            help="Fit skills that fall short of --min-students anyway. The "
                 "measurements in this file's docstring say the result will "
                 "very likely be worse than the prior it replaces.",
        )

        # Trigger: python manage.py fit_bkt --recompute-mastery
        parser.add_argument(
            "--recompute-mastery", action="store_true",
            help="After applying, replay every recorded attempt so stored "
                 "SkillMastery values match the new parameters. Without this "
                 "they keep reflecting the parameters they were computed under.",
        )


    # Function to define what to do when arguments are passed
    def handle(self, *args, **options):

        # Retrieve the full list of micro skills
        skills = MicroSkill.objects.filter(is_active=True).order_by("form_level", "order")

        # If argument passed is skill, filter the list to only that skill
        if options["skill"]:
            skills = skills.filter(slug=options["skill"])
            if not skills.exists():
                raise CommandError(f"No active micro-skill with slug {options['skill']!r}.")

        # Perform reset on skills by triggering the _reset() function
        if options["reset"]:
            return self._reset(skills, options)

        # Retrieve the attempt sequences for each skill (only the ones satisfying min_attempts)
        sequences = self._sequences_by_skill(skills, options["min_attempts"])

        # Fit the BKT model to the attempt sequence and output the results
        rows = self._fit_all(skills, sequences, options)
        self._report(rows, options)

        # Only print results if --apply is not specified
        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                "\nNothing was written. Re-run with --apply to keep the fits marked APPLY."))
            return

        # Apply the fitted parameters and recompute mastery if necessary
        applied = self._apply(rows)
        self.stdout.write(self.style.SUCCESS(f"\nApplied {applied} fit(s)."))
        if applied and options["recompute_mastery"]:
            self._recompute_mastery()
        elif applied:
            self.stdout.write(self.style.WARNING(
                "Stored SkillMastery values still reflect the old parameters. "
                "Re-run with --recompute-mastery to rebuild them from the "
                "recorded attempts."))


    # A function to retrieve the attempt sequence for each skill
    def _sequences_by_skill(self, skills, min_attempts):

        from learning.models import Attempt

        # Retrieve each attempt and arrange based on student_id and created_at
        by_skill = {}
        rows = (
            Attempt.objects.filter(micro_skill__in=skills)
            .order_by("student_id", "created_at", "id")
            .values_list("micro_skill_id", "student_id", "is_correct")
        )

        # Build a dictionary to represent the attempts
        for skill_id, student_id, correct in rows:
            by_skill.setdefault(skill_id, {}).setdefault(student_id, []).append(bool(correct))

        # Only return the attempts that exceed the threshold
        return {
            skill_id: {s: seq for s, seq in students.items() if len(seq) >= min_attempts}
            for skill_id, students in by_skill.items()
        }


    # A function to perform BKT fitting on each skill
    def _fit_all(self, skills, sequences, options):

        # Loop through each skill
        rows = []
        fitter = None
        for skill in skills:

            # Retrieve the number of students who attempted the skill
            students = sequences.get(skill.id, {})
            n = len(students)

            # Create a dict to store details of the fitting process
            row = {
                "skill": skill,
                "students": n,
                "attempts": sum(len(v) for v in students.values()),
                "current": bkt.params_for(skill),
                "fitted": None,
                "status": "",
            }

            # Check if the number of students exceeds the threshold
            if n < options["min_students"] and not options["force"]:
                row["status"] = f"SKIP (needs {options['min_students']} students)"
                rows.append(row)
                continue

            # No fitting if there's only one student
            if n < 2:
                row["status"] = "SKIP (too few sequences to fit)"
                rows.append(row)
                continue

            # Initialize fitter if it is not
            if fitter is None:
                fitter = self._load_fitter()

            # Perform fitting
            try:
                raw = fitter(list(students.values()))

            # If error happens, try the next skill
            except Exception as exc:
                row["status"] = f"FAILED ({type(exc).__name__}: {exc})"
                rows.append(row)
                continue

            # Perform shrinkage if necessary
            fitted = raw if options["no_shrink"] else bkt.shrink_towards(raw, n)

            # Append the results to the dictionary and the main list
            row["raw"] = raw
            row["fitted"] = bkt.bound_params(fitted)
            row["status"] = "APPLY"
            rows.append(row)

        # Return the main list of results once done
        return rows


    # A function to initialize the libraries and function to fit BKT
    def _load_fitter(self):

        # Load the libraries
        try:
            import pandas as pd
            from pyBKT.models import Model
        except ImportError as exc:
            raise CommandError(
                "This command needs pyBKT and pandas:\n"
                "    pip install pyBKT pandas\n"
                f"({exc})"
            )

        # Declare the function to perform fitting
        def fit(sequences):

            # Build a table to represent the answering attempts
            rows = [
                (student_index, "skill", int(correct))
                for student_index, seq in enumerate(sequences)
                for correct in seq
            ]
            frame = pd.DataFrame(rows, columns=["user_id", "skill_name", "correct"])

            # Build a pyBKT model and feed the table to train it
            model = Model(seed=42, num_fits=5, parallel=False)
            model.fit(data=frame, defaults={
                "user_id": "user_id", "skill_name": "skill_name", "correct": "correct"})

            # Retrieve and return the fitted parameters
            values = {r["param"]: r["value"] for _, r in model.params().reset_index().iterrows()}
            return BKTParams(
                p_init=values["prior"],
                p_transit=values["learns"],
                p_slip=values["slips"],
                p_guess=values["guesses"],
            )

        # Return the fit() function
        return fit


    # A function to print the outputs
    def _report(self, rows, options):

        # Print the minimum students and minimum attempts required
        self.stdout.write(
            f"Gates: at least {options['min_students']} students per skill, "
            f"each with at least {options['min_attempts']} attempts on it."
        )

        # Print the initial BKT parameters
        prior = bkt.INITIAL_PARAMS
        self.stdout.write(
            f"Shipped prior: init={prior.p_init} transit={prior.p_transit} "
            f"slip={prior.p_slip} guess={prior.p_guess}"
        )

        # Print if shrinkage is applied
        self.stdout.write(
            f"Shrinkage towards it: {'off (--no-shrink)' if options['no_shrink'] else 'on'}\n"
        )

        # Create a table
        header = (
            f"{'skill':<38} {'stud':>5} {'att':>6}  {'init':>6} {'trans':>6} "
            f"{'slip':>6} {'guess':>6}  status"
        )
        self.stdout.write(header)
        self.stdout.write("-" * len(header))

        # For each skill detail (represented in rows)
        for row in rows:

            # Print the current details of the skill (before fitting)
            cur = row["current"]
            self.stdout.write(
                f"{row['skill'].slug:<38} {row['students']:>5} {row['attempts']:>6}  "
                f"{cur.p_init:>6.3f} {cur.p_transit:>6.3f} {cur.p_slip:>6.3f} "
                f"{cur.p_guess:>6.3f}  now"
            )

            # If the skill fails to get updated, print empty lines with warnings
            if row["fitted"] is None:
                self.stdout.write(f"{'':<38} {'':>5} {'':>6}  {'':>6} {'':>6} {'':>6} {'':>6}  "
                                  + self.style.WARNING(row["status"]))
                continue

            # Print the updated details of the skill (after fitting)
            new = row["fitted"]
            self.stdout.write(
                f"{'':<38} {'':>5} {'':>6}  "
                f"{new.p_init:>6.3f} {new.p_transit:>6.3f} {new.p_slip:>6.3f} "
                f"{new.p_guess:>6.3f}  " + self.style.SUCCESS(row["status"])
            )

            # A small test, if a student provides a wrong answer, will mastery decrease?
            after = bkt.update(0.30, False, new)
            if after > 0.30:
                self.stdout.write(self.style.ERROR(
                    f"{'':<38} WARNING: under this fit a wrong answer raises mastery "
                    f"(0.300 -> {after:.3f}). Do not apply it."
                ))


    # A function to apply the newly fitted BKT params into the system and database
    def _apply(self, rows):

        # Make sure that each apply is atomic
        applied = 0
        with transaction.atomic():

            # For each skill
            for row in rows:

                # If the skill is not updated, skip it
                if row["fitted"] is None:
                    continue

                # Update the new BKT params to system and database
                skill, new = row["skill"], row["fitted"]
                skill.bkt_p_init = new.p_init
                skill.bkt_p_transit = new.p_transit
                skill.bkt_p_slip = new.p_slip
                skill.bkt_p_guess = new.p_guess
                skill.bkt_fitted_at = timezone.now()
                skill.bkt_fit_attempts = row["attempts"]
                skill.save(update_fields=[
                    "bkt_p_init", "bkt_p_transit", "bkt_p_slip", "bkt_p_guess",
                    "bkt_fitted_at", "bkt_fit_attempts",
                ])
                applied += 1

        # Return the number of counts of skills with updated params
        return applied

    # A function to write back the BKT parameters from dataset training
    def _reset(self, skills, options):

        # Retrieve the initial parameters from the BKT class
        prior = bkt.INITIAL_PARAMS

        # If apply is not specified, just print
        if not options["apply"]:
            self.stdout.write(
                f"Would restore {skills.count()} skill(s) to the pooled prior: "
                f"init={prior.p_init} transit={prior.p_transit} "
                f"slip={prior.p_slip} guess={prior.p_guess}"
            )
            self.stdout.write(self.style.WARNING(
                "Nothing was written. Re-run with --reset --apply."))
            return

        # Else, update all the BKT parameters based on the initial params
        n = skills.update(
            bkt_p_init=prior.p_init, bkt_p_transit=prior.p_transit,
            bkt_p_slip=prior.p_slip, bkt_p_guess=prior.p_guess,
            bkt_fitted_at=None, bkt_fit_attempts=0,
        )
        self.stdout.write(self.style.SUCCESS(f"Restored {n} skill(s) to the pooled prior."))

        # Recompute the mastery of each student if the argument is passed in
        if options["recompute_mastery"]:
            self._recompute_mastery()


    # A function to recalculate the student mastery based on the current BKT params
    def _recompute_mastery(self):

        from learning.models import Attempt, SkillMastery

        # Retrieve all learning attempts of students from the system
        sequences = {}
        for attempt in Attempt.objects.order_by("created_at", "id").values_list(
            "student_id", "micro_skill_id", "is_correct"
        ):
            sequences.setdefault(attempt[:2], []).append(attempt[2])

        # Perform recalculation
        changed = 0
        with transaction.atomic():

            # For each micro skill
            for mastery in SkillMastery.objects.select_related("micro_skill"):

                # Retrieve the stored BKT parameters
                params = bkt.params_for(mastery.micro_skill)
                value = params.p_init

                # Recalculate the BKT parameters based on each attempt
                for correct in sequences.get((mastery.student_id, mastery.micro_skill_id), []):
                    value = bkt.update(value, correct, params)

                # Only perform rewrite to system and database if there is difference
                if abs(value - mastery.bkt_mastery) > 1e-9:
                    mastery.bkt_mastery = value
                    mastery.save(update_fields=["bkt_mastery"])
                    changed += 1

        # Output to terminal once done
        self.stdout.write(self.style.SUCCESS(
            f"Recomputed mastery: {changed} row(s) updated."))
