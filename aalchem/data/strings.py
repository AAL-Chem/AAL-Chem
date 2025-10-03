import nltk
import json
import re
from colorama import Fore, Style, Back
from typing import List, Tuple, Optional, Dict, Any, abstractmethod


class Token:
    def __init__(
        self,
        text: str,
        index: Optional[int] = None,
        color: Optional[str] = '',
        bg: Optional[str] = None,
        aligned: bool = False,
        original: Optional["Token"] = None,
        operation: Optional[str] = None,
        start: Optional[int] = None,
        alignment_spaces: Optional[int] = 0,
    ):
        """
        Initialize a Token object.

        Args:
            text: The text content of the token
            index: Position index of the token
            color: Color code for display
            bg: Background color code for display
            aligned: Whether the token is aligned
            original: Original token object
            operation: Operation applied to the token
            start: Start position of the token
            alignment_spaces: Number of spaces to align the token
        """
        self.text = text
        self.index = index
        self.start = start
        self.aligned = aligned
        self.alignment_spaces = alignment_spaces
        self.color = color
        self.bg = bg
        self.original = original
        self.operation = operation
    
    @abstractmethod
    def get_matching_operation(self) -> str:
        pass

    def __len__(self) -> int:
        return self.length

    def __eq__(self, other: "Token") -> bool:
        return self.text == other.text

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}@[{self.index}]: {self.text}"

    def summary(self) -> str:
        start, end = self.pos
        t = ""
        if self.original is not None:
            t = self.original.text
        return f"{self.index:3}: [{str(start)}, {str(end):10}], l=[{len(self):2}]  |  {self.__class__.__name__:12}  |  {self.text:15} | {t:9}"

    @property
    def length(self):
        return len(self.text)

    @property
    def pos(self) -> Tuple[int, int]:
        """
        Absolute position of the token in the Text object
        """
        return self.start, self.start + len(self)

    @property
    def text_aligned(self) -> str:
        """
        Grazina teksta su pridetais tarpais, jei buvo atliktas alignment
        """
        string = self.text
        if self.aligned:
            string = self.text + "=" * self.alignment_spaces
        return string

    @property
    def text_formatted(self) -> str:
        """
        Grazina formatuota teksta
        Pvz. su spalvomis jei alignmente buvo nurodyta
        """
        string = self.text_aligned
        bg = "" if self.bg is None else f"{self.bg}"
        if self.color is not None:
            string = f"{self.color}{bg}{string}{Style.RESET_ALL}"
        return string

    def clear_alignment(self):
        self.aligned = False
        self.alignment_spaces = 0
        self.color = None

    def set_color(self, color: str) -> str:
        """
        Set the color for token display.
        Args:
            color: Color code ('b', 'r', 'g', 'p')
        Returns:
            str: The ANSI color code
        """
        self.color = COLOR_MAPPING[color]
        return self.color

    def set_bg(self, color: str) -> str:
        """
        Set the background color for token display.
        """
        bg_mapping = {"w": Back.WHITE, "b": Back.BLACK, "y": Back.YELLOW}
        self.bg = bg_mapping[color]
        return self.bg

    def set_formatting(self, formatting: str) -> str:
        """
        Set the formatting (bold, italic, underline, etc.)
        """
        if 'b' in formatting:
            self.color += '\x1b[1m'
        elif 'i' in formatting:
            self.color += '\x1b[3m'
        elif 'u' in formatting:
            self.color += '\x1b[4m'
        elif 's' in formatting:
            self.color += '\x1b[9m'
        return self.color

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the Token object to a dictionary suitable for JSON serialization.
        """
        return {
            "type": self.__class__.__name__,
            "text": self.text,
            "index": self.index,
            "color": self.color,
            "bg": self.bg,
            "original": self.original.to_dict() if self.original else None,
            "operation": self.operation,
            "start": self.start,
            "aligned": self.aligned,
            "alignment_spaces": self.alignment_spaces,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Token":
        """
        Create a Token object from a dictionary representation.
        """
        # Convert color name back to colorama color if it exists
        if data["color"] is not None:
            color_code = data["color"].lower()
            color_code = COLOR_MAPPING.get(color_code)
        else:
            color_code = None

        # Create original token if it exists
        original = None
        if data["original"]:
            original = cls.from_dict(data["original"])
        if data["original"]:
            original = cls.from_dict(data["original"])

        # Create appropriate token type based on the stored type
        token_class = globals()[data['type']]
        token = token_class(
            text=data["text"],
            index=data["index"],
            color=color_code,
            bg=data["bg"],
            aligned=data["aligned"],
            original=original,
            operation=data["operation"],
            start=data["start"],
            alignment_spaces=data["alignment_spaces"],
        )
        return token


### Token subclasses
class Whitespace(Token):
    """
    Is not used by default, but only when there are multiple spaces in a row.
    """
    def __init__(self, text: str = " ", **kwargs):
        super().__init__(text=text, **kwargs)


class Spacer(Token):
    """
    Dummy token, inserted after alignment, text is empty, but alignment_spaces are set
    """
    def __init__(self, text: str = '', **kwargs):
        super().__init__(text=text, **kwargs)


class Punctuation(Token):
    """
    Gal reikes kazkokios papildomos logikos ateity skyrybos zenklams
    """
    def __init__(self, text: str, **kwargs):
        super().__init__(text=text, **kwargs)


class Word(Token):
    """
    Word token

    Has a hunspell suggestions function
    """
    def __init__(self, text: str, **kwargs):
        super().__init__(text=text, **kwargs)

class Special(Token):
    """
    Special tokens (\n, \t, ...)
    """
    def __init__(self, text: str, **kwargs):
        super().__init__(text=text, **kwargs)


class Numeric(Token):
    """
    Numeric token
    """
    def __init__(self, text: str, **kwargs):
        super().__init__(text=text, **kwargs)



###################
### Constants
###################
COLOR_MAPPING = {
    "b": Fore.BLUE,
    "r": Fore.RED,
    "g": Fore.GREEN,
    "p": Fore.MAGENTA,
    "y": Fore.YELLOW,
    "c": Fore.CYAN,
    "w": Fore.WHITE,
    "k": Fore.BLACK,
}

PUNCTUATION_MARKS = frozenset(    
    [
        ".",
        ",",
        "!",
        "?",
        ":",
        ";",
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        '"',
        "'",
        "-",
        "—",
        "–",
        "…",
        "„",
        "“",
        "”",
        "''",
        '"',
    ]
)

WORD_PATTERN = re.compile(r"^[A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž0-9\'-.]+$")

###################
### Token creation
###################

def create_token(text: str, **kwargs) -> Token:
    """
    Creates a token object based on the type of the input text.

    Args:
        text: The text content to create a token from
        **kwargs: Additional arguments to pass to the token constructor

    Returns:
        Token: A new token object of the appropriate subclass
    """
    if text == " ":
        return Whitespace(text=text, **kwargs)
    elif text in PUNCTUATION_MARKS:
        return Punctuation(text=text, **kwargs)
    elif text.isdigit():
        return Numeric(text=text, **kwargs)
    elif WORD_PATTERN.match(text):
        return Word(text=text, **kwargs)
    elif text == "":
        return Spacer(text=text, **kwargs)
    elif text in ["\n", "\t"]:
        return Special(text=text, **kwargs)
    else:
        return Token(text=text, **kwargs)
    

def reconstruct_text_with_rules(tokens: List[Token]) -> str:
    """
    Reconstructs a string from tokens, applying rules to handle spacing.

    Args:
        tokens: A list of token strings.

    Returns:
        The reconstructed string.
    """
    text = ""
    for i, token in enumerate(tokens):
        ### BUG
        if isinstance(token.text, Token):
            text += token.text.text
        else:
            text += token.text
        if i + 1 < len(tokens):
            next_token = tokens[i + 1]
            no_space_token = ( ## Tokens before which whitespaces are not added
                isinstance(next_token, Whitespace)
                or isinstance(next_token, Spacer)
                or isinstance(next_token, Punctuation)
            )
            text += "" if no_space_token else " "
    return text


class Text:
    """
    Tokenu containeris
    1. Tokenu sukurimas is string
    2. Alignmentas
    3. Teksto atvaizdavimas
    4. Teksto kformatavimas
    """

    def __init__(self, string: str = None):
        self.tokens = self.from_string(string) if string is not None else []
        self._text = None
        self.recalculate_indices()

    def __str__(self):
        return self.to_string()

    def __getitem__(self, key):
        return self.tokens[key]

    def __len__(self):
        return len(self.tokens)
    
    def __repr__(self):
        return self.to_string()

    def __add__(self, other: "Text") -> "Text":
        return Text(self.to_string() + other.to_string())

    def from_string(self, string: str) -> List[Token]:
        tokens = []
        for token in whitespace_tokenize_from_nltk(string):
            tokens.append(create_token(token))
        self.tokens = tokens
        self.recalculate_indices()
        return tokens

    def to_string(self) -> str:
        return "".join([token.text for token in self.tokens])

    @property
    def text(self):
        if self._text is None:
            self._text = self.to_string()
        return self._text

    @property
    def text_aligned(self) -> str:
        return "".join([token.text_aligned for token in self.tokens])

    @property
    def text_formatted(self) -> str:
        return "".join([token.text_formatted for token in self.tokens])

    def insert(self, index: int, token: Token|None = None, string: str = None) -> None:
        """
        Go-to metodas, nauju tokenu iterpimui i teksta (nesumaiso indexu)
        """
        if token is None and string is not None:
            token = create_token(string)
        self.tokens.insert(index, token)
        self.recalculate_indices()

    def at_position(self, pos):
        for token in self.tokens:
            if token.start <= pos <= token.start + len(token):
                return token
        return None

    def insert_char(self, index: int, char: str) -> None:
        """
        Iterpia simboli i teksta

        TODO: reik checko, kuris ziures ar iterpiama i Whitespace ar i Word objekta
        1. Jei i Whitespace, reikes kurt nauja tokena
        2. Jei i Word, tiesiog iterpiam i token.text
        """
        token = self.at_position(index)
        if token is not None:
            token.text = (
                token.text[: index - token.start]
                + char
                + token.text[index - token.start :]
            )
            token.text = (
                token.text[: index - token.start]
                + char
                + token.text[index - token.start :]
            )
            self.recalculate_indices()
        else:
            print("No token found at position")

            print("No token found at position")

    def recalculate_indices(self):
        """
        Recalculates token.index and token.start values after changes are made to the tokens/text.
        """
        ## Update start positions (using two rules to add spaces when needed)
        start = 0
        for i, token in enumerate(self.tokens):
            token.index = i
            token.start = start
            next_token = self.tokens[i + 1] if i + 1 < len(self.tokens) else None
            no_space_needed = any(isinstance(next_token, t) for t in [Punctuation, Whitespace, Spacer])

            offset = 1 if next_token is not None and not no_space_needed else 0
            start += len(token) + offset
        self._text = self.to_string()  # Reset cached text
        self._text = self.to_string()  # Reset cached text

        return self.tokens

    def clear_alignment(self) -> "Text":
        for token in self.tokens:
            token.clear_alignment()

    def search(
        self, query: str, recalculate_indices: bool = True, substring=False
    ) -> List[Token]:
        """
        Returns a list of tokens that match the query.
        if substring is True, returns tokens that contain the query as a substring.
        """
        if recalculate_indices:
            self.recalculate_indices()
        if substring:
            return [token for token in self.tokens if query in token.text]
        else:
            return [token for token in self.tokens if token.text == query]

    def summary(self, verbose=False, max_lines: int = 100) -> List[str]:
        """
        Returns a summary of the text
        1. Text printed with cutoff
        2. Statistics
        3. Token list
        """
        spacing = 75
        spacer = "=" * spacing
        spacer = "=" * spacing

        lines = []

        n_lines = min((len(self.text) // spacing) + 1, max_lines)
        text_box = ["" for _ in range(n_lines)]
        non_spacer_tokens = [token for token in self.tokens if not isinstance(token, Spacer)]
        new_lines = [spacer, f"Text: {len(self.tokens)} ({len(non_spacer_tokens)}) tokens, {len(self.text)} characters", spacer]
        lines.extend(new_lines)
        for n, i in enumerate(range(0, len(self.text), spacing)):
            text_box[n] = self.text[i : i + spacing]
            if i + spacing > len(self.text) or n > max_lines:
                break
        lines.extend(text_box)

        lines.extend([spacer, "Tokens:"])
        for token in self.tokens:
            lines.append(token.summary())
        lines.append("=" * spacing)

        if verbose:
            for line in lines:
                print(line)
        return lines

    def compare(self, other: "Text") -> None:
        """
        Compares two Text objects and returns a list of tuples of tokens that are different.
        """
        ## Use summary to print out the differences
        compare_texts(self, other)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the Text object to a dictionary suitable for JSON serialization.
        """
        return {
            "tokens": [token.to_dict() for token in self.tokens],
            "text": self._text,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Text":
        """
        Create a Text object from a dictionary representation.
        """
        text_obj = cls()
        text_obj.tokens = [Token.from_dict(token_data) for token_data in data["tokens"]]
        text_obj._text = data["text"]
        text_obj.recalculate_indices()
        return text_obj

    def to_json(self) -> str:
        """
        Serialize the Text object to a JSON string.
        """
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> "Text":
        """
        Create a Text object from a JSON string.
        """
        return cls.from_dict(json.loads(json_str))


def compare_texts(text1: Text, text2: Text) -> None:
    """
    Compares two Text objects and returns a list of tuples of tokens that are different.
    """
    lines1 = text1.summary(verbose=False)
    lines2 = text2.summary(verbose=False)
    max_len = max(len(lines1), len(lines2))
    for i in range(max_len):
        line1 = lines1[i] if i < len(lines1) else ""
        line2 = lines2[i] if i < len(lines2) else ""
        print(f"{line1:75} |  {line2:75}  |")
    print("=" * 150)
    

def whitespace_tokenize_from_nltk(text):
    """
    Tokenizes text by incorporating whitespace characters from the original text
    into the output of nltk.word_tokenize.

    Iterates through nltk tokens and checks for whitespace following each token
    in the original text, adding each whitespace character as a separate token.

    Args:
        nltk_tokens (list): Output of nltk.word_tokenize for the original text.
        original_text (str): The original text string.

    Returns:
        list: A list of tokens, including words and whitespace characters,
              similar to the desired output.
    """
    result_tokens = []
    current_index = 0
    nltk_tokens = nltk.word_tokenize(text)
    for token in nltk_tokens:
        # Find the start index of the current nltk token in the original text
        start_token_index = text.find(token, current_index)

        if start_token_index == -1:
            # This should ideally not happen if nltk_tokens are correctly derived from original_text
            raise ValueError(f"Token '{token}' not found in original text from index {current_index} onwards.")

        # Add the nltk token to the result
        result_tokens.append(token)
        current_index = start_token_index + len(token)

        # Check for whitespace characters immediately after the token
        while current_index < len(text) and text[current_index].isspace():
            result_tokens.append(text[current_index])
            current_index += 1

    return result_tokens
