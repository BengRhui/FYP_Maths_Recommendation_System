"""
This file handles the checking of student's answer with the actual answer in the database
(for input-based questions).
"""

import ast
import math
import re

# The list of functions that students can use
_FUNCS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "ln": math.log,
    "log": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
}

# The only constant used in the system is π
_CONSTANTS = {"pi": math.pi}

# Safeguards to reject overly large answers to prevent overflow errors
_MAX_EXPONENT = 64
_MAX_MAGNITUDE = 1e15
_TOLERANCE = 1e-9

# Number of significant figures used to check decimal answers
_TOLERANCE_SIG_FIGURES = 3

# The samples used to evaluate if two expressions are equivalent
_SAMPLES = (0.7, -1.3, 2.4, -3.1, 4.6, -5.9, 7.3, 1.1)
_MIN_SAMPLE_HITS = 4

# The maximum number of distinct variables allowed (to handle invalid inputs easier)
_MAX_VARIABLES = 4

# Regex used to ensure that the answer is in the correct format: allowed checks for allowed characters, token removes characters in the wrong position
_TOKEN_RE = re.compile(r"\d+\.\d*|\.\d+|\d+|[a-z]+|\*\*|[-+*/^()]")
_ALLOWED_RE = re.compile(r"^[0-9a-z+\-*/^().\s]+$")

# Regex that defines the format of answers that are acceptable
_INTEGER_RE = re.compile(r"^[+-]?\d+$")                         # Integers only accept whole numbers
_FRACTION_RE = re.compile(r"^([+-]?\d+)/([+-]?\d+)$")           # Fraction accepts numerator / denominator format
_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)$")      # Decimal accepts numbers with or without decimal point
_SUBJECT_RE = re.compile(r"^\s*([A-Za-z])\s*=\s*(.+)$", re.S)

# A map to replace certain symbols with their equivalent characters
_SUBSTITUTIONS = {
    "−": "-",
    "–": "-",
    "—": "-",
    "×": "*",
    "·": "*",
    "÷": "/",
    "⋅": "*",
}

# The allowed operations that a student can key into the answer box
_ALLOWED_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)

# A function to check for equivalence between student answer and correct answer
def check(submitted, correct):

    # For questions like "x = y + z", the check splits the subject (x) and the body (y + z)
    subject, body = _split_subject(correct)

    # Formulae question check: if there is a subject, then proceed to check if the formula is correct
    if subject is not None:
        return _check_formula(submitted, subject, body)

    # Non-formulae question check: if there is no subject, then proceed to parse the expression
    parsed_correct = _parse(correct)

    # If the parsing fails, then the answer format is incorrect
    if parsed_correct is None:
        return False

    # If parsing is successful, store the output into two: a syntax tree + a variable set
    correct_node, correct_vars = parsed_correct

    # Expression question check: if there are variables, then check if expressions are equivalent
    if correct_vars:
        return _check_algebraic(submitted, correct_node, correct_vars)

    # Numeric question check: if there are no variables, check the value of the numeric answer
    correct_value = _value_of(correct_node)

    # If none is returned, the input cannot be evaluated
    if correct_value is None:
        return False

    # Integer check: If the value is an integer, check if the submitted answer matches
    if float(correct_value).is_integer():
        return _check_whole_number(submitted, correct_value)

    # Noninteger check: Evaluate if the fractions or decimals are equivalent to answer
    return _check_fractional(submitted, correct, correct_value)


# A function to check if the answer matches the integer value
def _check_whole_number(submitted, correct_value):

    # Clean the input
    text = _clean(submitted)

    # Check if the input is a valid integer format
    if not _INTEGER_RE.match(text):
        return False

    # Check if the values match
    return int(text) == int(correct_value)


# A function to check if the fraction or decimal answer is equivalent to the stored value
def _check_fractional(submitted, correct_text, correct_value):

    # Clean the text
    text = _clean(submitted)

    # Check the fraction regex to determine if it's a fraction
    submitted_fraction = _FRACTION_RE.match(text)
    if submitted_fraction:

        # Extract the correct fractional answer, then check if the numerator and denominator match
        correct_fraction = _FRACTION_RE.match(_clean(correct_text))
        if correct_fraction:
            return _fraction_parts(submitted_fraction) == _fraction_parts(correct_fraction)

        # If the correct answer is not a fraction, then round to nearest sf and determine if they match
        return _agrees_to_sig_figures(_fraction_value(submitted_fraction), correct_value)

    # Check the decimal regex to determine if it's a decimal, then check sf if yes
    if _DECIMAL_RE.match(text):
        return _agrees_to_sig_figures(float(text), correct_value)

    # If the answer is neither fraction nor decimal, it's a wrong answer
    return False


# A function to extract the numerator and denominator from a fraction
def _fraction_parts(match):

    # Extract the numerator and denominator
    numerator, denominator = int(match.group(1)), int(match.group(2))

    # Check for the case where denominator is negative, then flip signs
    if denominator < 0:
        numerator, denominator = -numerator, -denominator

    # Return the numerator and denominator
    return numerator, denominator


# A function to calculate the decimal value of a fraction
def _fraction_value(match):

    # Extract the numerator and denominator
    numerator, denominator = _fraction_parts(match)

    # Calculate the decimal values
    return numerator / denominator if denominator else None


# A function to check whether a decimal value is within tolerance of the fixed significant figures
def _agrees_to_sig_figures(value, correct_value, figures=_TOLERANCE_SIG_FIGURES):

    # Reject if the input value is empty or invalid
    if value is None:
        return False

    # If the correct value is zero, then directly check if the input value is also zero
    if correct_value == 0:
        return value == 0

    # For values other than zero, first extract the exponent of the standard form
    # Example: 1234.56 = 1.23456 x 10^3, so exponent is 3
    # The exponent represent the position of the first sf
    exponent = math.floor(math.log10(abs(correct_value)))

    # Tolerance is measured by the exponent value
    # Example: 1234.56 to 3 sf is 1230, the last position of sf is at the tens place (measured by: exponent_position - (TOLERANCE_SF - 1))
    # So the tolerance should be ±5, i.e., half of the tens place (measured by: 0.5 x 10 ^ last_sf_position)
    # Which gives the below formula:
    tolerance = 0.5 * 10 ** (exponent - (figures - 1))

    # Calculate if the difference between the input value and correct value is within tolerance
    return abs(value - correct_value) <= tolerance


# A function to check if the algebraic expressions are equivalent
def _check_algebraic(submitted, correct_node, correct_vars, check_shape=True):

    # Clean the input and reject if the input cannot be parsed
    parsed = _parse(submitted)
    if parsed is None:
        return False

    # Store the parsed output into two: a syntax tree + a variable set
    node, variables = parsed

    # If the variable set is different, then answer is wrong
    if variables != correct_vars or len(variables) > _MAX_VARIABLES:
        return False

    # If the expressions are not equivalent (by testing on sample values), then reject
    if not _agrees_on_samples(node, correct_node, sorted(variables)):
        return False

    # Lastly, check if the expressions are simplified
    return _is_finished(node, correct_node, check_shape)


# A function to split an algebraic formula into subject and body
def _split_subject(text):

    # Check if the input matches the algebraic formula regex
    match = _SUBJECT_RE.match(text or "")

    # If input is not in the form of formula, or if the body contains an equal sign
    if not match or "=" in match.group(2):
        return None, None

    # Return the subject and body
    return match.group(1).lower(), match.group(2)


# A function to check if the submitted formula matches the correct answer
def _check_formula(submitted, subject, body):

    # Parse the answer key and reject if answer cannot be parsed
    parsed_body = _parse(body)
    if parsed_body is None:
        return False

    # Split the parsed input into subject and body
    submitted_subject, submitted_body = _split_subject(submitted)

    # Check if the subject is present
    if submitted_subject is not None:

        # If subject does not match, then it fails
        if submitted_subject != subject:
            return False

        # Else, the body will be checked subsequently
        candidate = submitted_body

    # If the body still has an equal sign, then it fails
    elif "=" in (submitted or ""):
        return False

    # If the subject is not present but the body is fine, then the body will still be recorded
    else:
        candidate = submitted

    # Store the answer key into two components: syntax tree + variable set
    correct_node, correct_vars = parsed_body

    # Then, proceed to check if the body is equivalent to answer
    return _check_algebraic(candidate, correct_node, correct_vars, check_shape=False)


# A function to check if an algebraic expression is simplified
def _is_finished(node, correct_node, check_shape=True):

    # Reject for two cases: It has unevaluated arithmetic (1 + 1) or it has repeated variables multiplying (a * a)
    if _has_unevaluated_arithmetic(node):
        return False
    if _has_repeated_variable_factor(node):
        return False

    # Convert the expression into distinct terms (e.g. 2x+3 -> ['2x', '3'])
    terms = _additive_terms(node)
    signatures = []
    for term in terms:

        # Reject the case where one of the terms is zero (e.g., 2x + 0)
        if len(terms) > 1 and _is_constant(term) and _value_of(term) == 0:
            return False

        # Extract the variable-power structure of the term (e.g., x^2 * y -> [('x', 2), ('y', 1)])
        signature = _monomial_signature(term)

        # If the structure cannot be parsed, we shall not check for it, so stop the loop
        if signature is None:
            signatures = None
            break

        # If everything goes well, then add the structure to the list
        signatures.append(signature)

    # Reject if duplicate terms exists
    if signatures is not None and len(signatures) != len(set(signatures)):
        return False

    # If the correct answer is in factorized format
    if _factorised_bracket(correct_node) is not None:

        # Try to parse the input into factorized format, and reject if the input is not fully simplified
        # Note: Equality is checked beforehand, so not required here
        bracket = _factorised_bracket(node)
        if bracket is None or not _bracket_is_reduced(bracket):
            return False

    # Lastly, if the number of terms in answer > 1, then the number of terms for input should also be > 1
    if not check_shape:
        return True
    return (len(terms) > 1) == (_canonical_term_count(correct_node) > 1)


# A function to count the number of distinct terms
def _canonical_term_count(node):

    # Convert the expression into distinct terms (e.g. 2x+3 -> ['2x', '3'])
    terms = _additive_terms(node)

    # Then, convert each term into its variable-power structure (e.g., x^2 * y -> [('x', 2), ('y', 1)])
    signatures = [_monomial_signature(t) for t in terms]

    # If there is anything unhandled, then return the number of terms only
    if any(signature is None for signature in signatures):
        return len(terms)

    # If not, then return the count of distinct terms
    return len(set(signatures))


# A function to convert products into their individual factors (e.g. 2xy -> [2, x, y])
def _product_factors(node, factors=None):

    # This is a recursive function, so factors will accumulate over time
    if factors is None:
        factors = []

    # If the input is a multiplication operation, recursively extract the left and right factors
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        _product_factors(node.left, factors)
        _product_factors(node.right, factors)
        return factors

    # If the input is a unary operation, then recursively extract the operand
    # Example: -x -> - is op, x is operand
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _product_factors(node.operand, factors)

    # If the input cannot be separated, then add the factor to the list and return
    factors.append(node)
    return factors


# A function to find the bracketed factor in a factorized expression
def _factorised_bracket(node):

    # Convert the expression into product factors, and reject if there are less than 2 factors
    factors = _product_factors(node)
    if len(factors) < 2:
        return None

    # Extract the factors that are additive expressions (e.g., 2x + 3)
    brackets = [f for f in factors if len(_additive_terms(f)) > 1]

    # If there is more than one brackets, reject
    # Note: The question bank does not contain answers with multiple brackets, so it's safe
    if len(brackets) != 1:
        return None

    # Return the bracketed factor
    return brackets[0]


# A function to check if the bracketed term still contains common factors
def _bracket_is_reduced(bracket):

    # Extract each term in the bracket
    terms = _additive_terms(bracket)

    # If there is only one term, then it is fully simplified
    if len(terms) < 2:
        return True

    # Else, convert each term into its variable-power structure (e.g., x^2 * y -> [('x', 2), ('y', 1)])
    signatures = [_monomial_signature(term) for term in terms]

    # Skip the check if any of the terms cannot be parsed
    if any(signature is None for signature in signatures):
        return True

    # Extract the variables in the first term
    shared = {name for name, power in signatures[0] if power > 0}

    # Then check if the remaining terms share the same variables by performing intersection
    # For example, given xy + xz, the intersection will be {x}
    for signature in signatures[1:]:
        shared &= {name for name, power in signature if power > 0}

    # Reject if there are any shared variables
    if shared:
        return False

    # Check for coefficients
    coefficients = []
    for term in terms:

        # Extract the coefficient of each term
        value = _coefficient_of(term)

        # Do not check anything if the coefficient cannot be parsed
        if value is None or value != int(value) or value == 0:
            return True

        # If it can be parsed, then add the absolute value of the coefficient
        coefficients.append(abs(int(value)))

    # And check the highest common factor, if HCF is not 1 then it can still be factorized
    return math.gcd(*coefficients) == 1


# A function to find the coefficient of a term
def _coefficient_of(node):

    # Set each variable in the expression to 1
    env = {
        name.id: 1.0
        for name in ast.walk(node)
        if isinstance(name, ast.Name) and name.id not in _CONSTANTS
    }

    # Try to evaluate the expression and return the coefficient
    try:
        return _evaluate(node, env)

    # If the expression cannot be evaluated, return None
    except _Unevaluable:
        return None


# A function to list the additive terms of an expression (e.g. 2x + 3 -> [2x, 3])
def _additive_terms(node, terms=None):

    # This is a recursive function, so terms will accumulate over time
    if terms is None:
        terms = []

    # Recursively extract the left and right terms
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        _additive_terms(node.left, terms)
        _additive_terms(node.right, terms)
        return terms

    # If the input is a unary operation, then just extract the operand
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _additive_terms(node.operand, terms)

    # If the input cannot be split, then add the term to the list and return
    terms.append(node)
    return terms


# A function to retrieve the variable-power structure of a monomial
def _monomial_signature(node):

    # If the input is a constant (e.g., numbers), then return an empty set
    if isinstance(node, ast.Constant):
        return frozenset()

    # If the input is a variable (pure variable), then return with power 1
    if isinstance(node, ast.Name):
        return frozenset() if node.id in _CONSTANTS else frozenset({(node.id, 1)})

    # If the input is a unary operation (e.g., -x), then recursively extract the operand
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _monomial_signature(node.operand)

    # If the input is a binary operation
    if isinstance(node, ast.BinOp):

        # If it involves multiplication or division (e.g., x * y)
        if isinstance(node.op, (ast.Mult, ast.Div)):

            # Label multiplication as +1 and division as -1
            sign = 1 if isinstance(node.op, ast.Mult) else -1

            # Then recursively extract the left and right factors, and combine them
            return _combine_signatures(
                _monomial_signature(node.left), _monomial_signature(node.right), sign
            )

        # If it involves exponents (e.g., (x^3 * y)^2)
        if isinstance(node.op, ast.Pow):

            # Extract the base and exponent
            base = _monomial_signature(node.left)
            exponent = _value_of(node.right)

            # Return none if anything cannot be extracted
            if base is None or exponent is None or exponent != int(exponent):
                return None

            # Multiply the exponent to each power in the base
            return _scale_signature(base, int(exponent))

    # If the input is not parseable, return None
    return None


# A function to combine two monomial signatures
def _combine_signatures(left, right, sign):

    # If either side is invalid, return none
    if left is None or right is None:
        return None

    # Convert the left signature into a dictionary
    powers = dict(left)

    # Loop through the right signature, then combine the exponents by adding with the left
    for variable, exponent in right:
        powers[variable] = powers.get(variable, 0) + sign * exponent

    # Lastly, return the calculated signature
    return frozenset((v, e) for v, e in powers.items() if e)


# A function to scale every power in a monomial signature by a factor
def _scale_signature(signature, factor):
    return frozenset((v, e * factor) for v, e in signature if e * factor)


# A function to detect if a variable is repeatedly multiplied by itself (e.g., y^2 * y)
def _has_repeated_variable_factor(node):

    # Check if the node is a multiplication operation
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):

        # Convert the expression into their individual factors and extract the base factor
        bases = [_power_base(factor) for factor in _product_factors(node)]
        bases = [base for base in bases if base is not None]

        # If bases has duplicates, then a variable is repeated
        if len(bases) != len(set(bases)):
            return True

    # For the expression can be split, check the child recursively
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.expr) and _has_repeated_variable_factor(child):
            return True

    # If nothing is found, return false
    return False


# A function to extract the base of an exponent
def _power_base(node):

    # Remove the leading sign and perform checking recursively
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _power_base(node.operand)

    # If the node is a pure variable, then return the variable itself
    if isinstance(node, ast.Name):
        return None if node.id in _CONSTANTS else node.id

    # If the node is an exponent, then recursively extract the base
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
        return _power_base(node.left)

    # Return none for other scenarios that do not match
    return None


# A function to detect if there is any unfinished arithmetic (e.g., 1 + 1)
def _has_unevaluated_arithmetic(node):

    # Check if it is a binary operation
    if isinstance(node, ast.BinOp):

        # Return true if the operation is in the form of 1 + 2
        if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Pow)):
            if _is_constant(node.left) and _is_constant(node.right):
                return True

        # If not, recursively check the left and right terms
        return _has_unevaluated_arithmetic(node.left) or _has_unevaluated_arithmetic(node.right)

    # If it is a unary operation, check the operand
    if isinstance(node, ast.UnaryOp):
        return _has_unevaluated_arithmetic(node.operand)

    # If it is a function call (e.g., sin(100)), check the argument
    # Reject if it is a constant (sqrt(9) is unfinished), or if the argument has unfinished arithmetic
    if isinstance(node, ast.Call):
        return _is_constant(node.args[0]) or _has_unevaluated_arithmetic(node.args[0])

    # Return false if everything passes the check
    return False


# A function to check whether an expression is a constant
def _is_constant(node):

    # True if it is a number
    if isinstance(node, ast.Constant):
        return True

    # True if it is a constant variable
    if isinstance(node, ast.Name):
        return node.id in _CONSTANTS

    # Evaluate the operand if the node is a unary operation (e.g. -3)
    if isinstance(node, ast.UnaryOp):
        return _is_constant(node.operand)

    # Evaluate the left and right operands if the node is a binary operation (e.g. 1 + 2)
    if isinstance(node, ast.BinOp):
        return _is_constant(node.left) and _is_constant(node.right)

    # Evaluate the argument if the node is a function call (e.g. sqrt(9))
    if isinstance(node, ast.Call):
        return _is_constant(node.args[0])

    # If none of the above, return false
    return False


# A function to clean raw inputs from students
def _clean(raw):

    # Convert everything to lowercase and remove trailing whitespaces
    text = (raw or "").lower().strip()

    # If there is any characters that can be substituted, then replace them
    for char, replacement in _SUBSTITUTIONS.items():
        text = text.replace(char, replacement)

    # Remove the commas for thousands separators
    text = re.sub(r"(?<=\d),(?=\d\d\d\b)", "", text)

    # Remove any whitespace in the input
    return text.replace(" ", "")


# A function to convert raw input into a syntax tree and a variable set
def _parse(raw):

    # Clean the input
    text = _clean(raw)

    # Check if it contains any illegal characters
    if not text or not _ALLOWED_RE.match(text):
        return None

    # Check if the input can be tokenized correctly (any symbols inputted in wrong position)
    tokens = _TOKEN_RE.findall(text)
    if "".join(tokens) != text:
        return None

    # Split the terms into individual variables
    tokens, variables = _expand_words(tokens)
    if tokens is None:
        return None

    # For consecutive terms, insert the multiplication sign
    # Example: ['2', 'x', 'y'] becomes '2 * x * y'
    source = "".join(_with_implicit_products(tokens)).replace("^", "**")

    # Try to parse the expression into the syntax tree (by using Python's AST)
    try:
        tree = ast.parse(source, mode="eval")

    # Reject if there is any syntax error or the expression is wrong
    except SyntaxError:
        return None
    if not _is_arithmetic(tree.body):
        return None

    # Return the syntax tree and the variable set if there is no error
    return tree.body, variables


# A function to split variable into individual letters
def _expand_words(tokens):

    # The place to store the outputs and variable set
    out = []
    variables = set()

    # Loop through each token
    for index, token in enumerate(tokens):

        # If the token is not an alphabet (numbers and operators), just add to output and continue
        if not token.isalpha():
            out.append(token)
            continue

        # Extract the next character after the current token
        following = tokens[index + 1] if index + 1 < len(tokens) else ""

        # If the token is a function, just add to output
        if token in _FUNCS and following == "(":
            out.append(token)
            continue

        # If the token is a constant, just add to output
        if token in _CONSTANTS:
            out.append(token)
            continue

        # If the token is a function but does not have a following "(", immediately reject
        if token in _FUNCS:
            return None, variables

        # For any other tokens, split them into individual letters
        for letter in token:
            out.append(letter)
            variables.add(letter)

    # Once done, return the output and variable set
    return out, variables


# A function to insert multiplication signs between adjacent variables
def _with_implicit_products(tokens):

    # Loop through each token
    out = []
    for index, token in enumerate(tokens):
        if index:

            # Extract the previous token
            previous = tokens[index - 1]

            # Check if the previous token ends with ), a digit, or a variable
            ends_value = previous == ")" or previous[0].isdigit() or (
                previous.isalpha() and previous not in _FUNCS
            )

            # Check the current token and see if it starts with (, a digit, or a variable
            starts_value = token == "(" or token[0].isdigit() or token.isalpha()

            # If both are terms (no operations), then insert a multiplication sign
            if ends_value and starts_value:
                out.append("*")

        # Once checked, add the current token to the output
        out.append(token)

    # And return the full output
    return out


# A function to screen through the syntax tree and determine if the expression is valid
def _is_arithmetic(node):

    # Make sure that constants are only integers and floats
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)

    # Make sure that pure variables are only single letters or constants
    if isinstance(node, ast.Name):
        return len(node.id) == 1 or node.id in _CONSTANTS

    # Make sure that unary operations are only + or - and the operand is valid
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, (ast.UAdd, ast.USub)) and _is_arithmetic(node.operand)

    # Make sure that binary operations only contains allowed operations, and both operands are valid
    if isinstance(node, ast.BinOp):
        return (
            isinstance(node.op, _ALLOWED_OPS)
            and _is_arithmetic(node.left)
            and _is_arithmetic(node.right)
        )

    # Make sure that the function calls are valid
    if isinstance(node, ast.Call):
        return (
            isinstance(node.func, ast.Name)         # Only names allowed (e.g., math.sqrt is not allowed)
            and node.func.id in _FUNCS              # The function must be in the allowed list
            and not node.keywords                   # No keyword arguments allowed (e.g., sqrt(x=9) is not allowed)
            and len(node.args) == 1                 # Only one argument is allowed
            and _is_arithmetic(node.args[0])        # The argument must be valid
        )

    # For any other cases, it is invalid, so return false
    return False


# A class that represents a custom exception to indicate that an expression cannot be evaluated
class _Unevaluable(Exception):
    pass


# A function to compute the numeric value of an expression without any variables
def _value_of(node):
    try:
        return _evaluate(node, {})
    except _Unevaluable:
        return None


# A function to recursively evaluate an expression given variable values
def _evaluate(node, env):

    # If the input is a constant, return the value itself
    if isinstance(node, ast.Constant):
        return float(node.value)

    # If the input is a variable
    if isinstance(node, ast.Name):

        # Return the constant value
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]

        # If it's not a constant, return the value from the environment
        try:
            return env[node.id]
        except KeyError:
            raise _Unevaluable

    # If the input is a unary operation, evaluate the operand and apply the correct sign
    if isinstance(node, ast.UnaryOp):
        value = _evaluate(node.operand, env)
        return -value if isinstance(node.op, ast.USub) else value

    # If the input is a binary operation, evaluate both operands and apply the operator
    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left, env)
        right = _evaluate(node.right, env)
        return _apply(node.op, left, right)

    # If the input is a function call, evaluate the argument and apply the function
    if isinstance(node, ast.Call):
        return _guard(_FUNCS[node.func.id], _evaluate(node.args[0], env))

    # If input does not match, then raise an exception
    raise _Unevaluable


# A function to apply a binary arithmetic operator to operands
def _apply(op, left, right):

    # Apply the corresponding operation based on operator type
    try:
        if isinstance(op, ast.Add):
            result = left + right
        elif isinstance(op, ast.Sub):
            result = left - right
        elif isinstance(op, ast.Mult):
            result = left * right
        elif isinstance(op, ast.Div):
            result = left / right
        elif isinstance(op, ast.Mod):
            result = math.fmod(left, right)
        else:
            if abs(right) > _MAX_EXPONENT:
                raise _Unevaluable
            result = left ** right

    # Raise exceptions if errors surface
    except (ZeroDivisionError, OverflowError, ValueError):
        raise _Unevaluable
    if isinstance(result, complex):
        raise _Unevaluable

    # Return the result if no errors are raised
    return _finite(result)


# A function to safely evaluate a function
def _guard(func, value):

    # Evaluate a function
    try:
        return _finite(func(value))

    # Raise exceptions if errors surface
    except (ValueError, OverflowError, ZeroDivisionError):
        raise _Unevaluable


# A function to validate that the calculated value is within the boundaries set
def _finite(value):

    # Check if the value is finite, and if it is within the maximum magnitude
    value = float(value)
    if not math.isfinite(value) or abs(value) > _MAX_MAGNITUDE:
        raise _Unevaluable

    # Return the value if it passes the checks
    return value


# A function to check whether two numbers are close (to prevent floating point precision issues)
def _close(left, right):
    return math.isclose(left, right, rel_tol=_TOLERANCE, abs_tol=_TOLERANCE)


# A function to check whether two expressions are equivalent for different inputs
def _agrees_on_samples(left, right, variables):

    # Loop through each input sample
    hits = 0
    for sample in _SAMPLES:

        # Define the input values for each variable
        env = {
            name: sample + position * 1.7
            for position, name in enumerate(variables)
        }

        # Attempt to evaluate both expressions
        try:
            if not _close(_evaluate(left, env), _evaluate(right, env)):
                return False

        # If exceptions arise, use another set of sample
        except _Unevaluable:
            continue

        # Increment hit count if evaluation is successful
        hits += 1

    # Return true if the number of successful evaluations meets the minimum
    return hits >= _MIN_SAMPLE_HITS
