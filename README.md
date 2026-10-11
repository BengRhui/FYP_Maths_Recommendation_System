
# FYP Project - Mathematics Question Recommendation System
---
## Introduction

Hi everyone! This is the repository for my FYP project.
This system is a mathematics question recommendation system built for Malaysian students.
How it works is that:
1. A machine learning model is first trained to predict the probability of a student answering a question correctly.
2. The predicted probabilites are inputted into the revised PEAR ranking formula:
    > $$[1 - 2|0.5 - P(\text{correct)}|] \times \text{cos_sim}(\text{Student mastery vector}, \text{Question skill vector})$$
3. Each question is assigned with a score, where the one with the highest score will be recommended to students.

Feel free to explore the system!

---

## How to run the system?

Run these commands in your terminal to run the system in action:

```bash
# Step 0: Python version
# Make sure that you're running Python 3.12 to avoid any dependency issues. You can check your Python version by running:
python --version

# Step 1: Activate the virtual environment
python -m venv .venv

.venv\Scripts\activate    # For Windows
source .venv/bin/activate # For macOS or Linux

# Step 2: Install dependencies/libraries from the requirements.txt file
pip install -r requirements.txt

# Step 3: Configure environment variables
# Note: Make sure to copy .env.example to .env, and change the configurations accordingly
cp .env.example .env

# Step 4: Apply migrations to build database schema
python manage.py migrate

# Step 5: Run the server
python manage.py runserver
```
Here are some credentials that you can use to log in once running the project:

| Role    | Email                | Password          |
|---------|----------------------|-------------------|
| Teacher | `teacher_1@mail.com` | `Abcdefg@1234567` |
| Student | `student_1@mail.com` | `Abcdefg@1234567` |
| Admin   | `admin@mail.com`     | `Abcdefg@1234567` |

Of course, you may also register a new user and play around with the system.

For teacher registration, the registration code is `ADEPTMATH-TEACHER-2026` in default. Refer to the `.env` file if you have changed the code.

---

## Machine Learning Pipeline

The machine learning pipeline is implemented in `research/pipeline/`. Run the notebooks in order to train the model.

1. Run the `1_preprocessing.ipynb` notebook to clean the dataset.
2. Run the `2_exploration.ipynb` notebook to explore the dataset (optional).
3. Run the `3_training.ipynb` notebook to train the model.

---

## Student Mastery Estimation

The BKT model is implemented to estimate student mastery on the platform.
Currently, due to the lack of student attempts, the BKT parameters used are the average from the BKT model trained from the ASSISTments dataset.

Once there is sufficient student data, the student attempt data in this system can be used to train the BKT model instead of relying on the precomputed BKT parameters, using the command:

```bash
python manage.py fit_bkt                              # only report what will be the changes
python manage.py fit_bkt --apply --recompute-mastery  # apply the new fits and recompute mastery for all students
python manage.py fit_bkt --reset --apply              # revert back to the precomputed BKT parameters
```

This shall only be executed by the system administrators when student data is sufficient.

---

## Technical Details of the Current Project

- Website Development Framework: Django
- Database: SQLite (can be migrated to PostgreSQL for future deployment)
- Machine Learning Model implemented:
  - Decision Tree
  - **CatBoost** (champion model)
  - Logistic Regression
  - Linear SVM
- Metrics evaluated:
  - ROC-AUC
  - Log-loss
  - Brier score

---

## Final Note

Thank you for reading until here. Have fun exploring the system! ⭐️
