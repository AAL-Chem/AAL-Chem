import matplotlib.pyplot as plt
from typing import Tuple
from aalchem.data.strings import Text, Spacer

## Main alignment functions
def align_sentences(text1: Text, text2: Text, verbose=False, visualize=False) -> Tuple[Text, Text]:
    """
    Main function to align two Text objects.
    """
    score_matrix, traceback_matrix = needleman_wunsch_alignment_words_substring(text1, text2)
    s1_aligned, s2_aligned = get_alignment_and_visualization_words(text1, text2, score_matrix, traceback_matrix)
    s1_aligned.recalculate_indices()
    s2_aligned.recalculate_indices()
    if visualize:
        visualize_alignment(text1, text2, score_matrix, traceback_matrix)

    return s1_aligned, s2_aligned


def align_strings(s1: str, s2: str, verbose=False, visualize=False) -> Tuple[Text, Text]:
    """
    Aligns two strings.
    """
    text1 = Text(s1)
    text2 = Text(s2)
    return align_sentences(text1, text2, verbose, visualize)


def visualize_alignment(text1: Text, text2: Text, score_matrix, traceback_matrix):
    """
    Visualizes the alignment of two texts.
    """
    # Set font size
    plt.rcParams.update({'font.size': 6})
    fig, axs = plt.subplots(1, 2, figsize=(10, 10))
    ## Subplot for the score matrix
    axs[0].imshow(score_matrix, cmap='viridis', interpolation='nearest')
    axs[0].set_title('Alignment Score Matrix')
    axs[0].set_xticks(range(len(text2.tokens)))
    axs[0].set_yticks(range(len(text1.tokens)))
    axs[0].set_xticklabels([t.text for t in text2.tokens], rotation=90)
    axs[0].set_yticklabels([t.text for t in text1.tokens])

    
    ## Subplot for the traceback matrix
    ## Convert the traceback matrix to integers
    traceback_matrix = [[1 if x == 'D' else 0 for x in row] for row in traceback_matrix]
    axs[1].imshow(traceback_matrix, cmap='viridis', interpolation='nearest')
    axs[1].set_title('Traceback Matrix')
    axs[1].set_xticklabels([t.text for t in text2.tokens], rotation=90)
    axs[1].set_yticklabels([t.text for t in text1.tokens])
    
    plt.tight_layout()
    plt.show()
    

#############
### Alignment logic 
def longest_common_substring(s1, s2):
    """
    Finds the longest common substring between two strings.
    """
    n = len(s1)
    m = len(s2)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    length = 0
    row, col = 0, 0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > length:
                    length = dp[i][j]
                    row = i
            else:
                dp[i][j] = 0
    if length == 0:
        return ""
    
    return s1[row - length:row]


def needleman_wunsch_alignment_words_substring(
        text1: Text, 
        text2: Text, 
        match_score=1,     # Match score
        mismatch_score=-1, # Mismatch penalty
        gap_score=-1,   # Gap penalty
        substring_match_score=1.5,  #  Matching substrings of different lengths
        type_match_score=.5,      #  Matching tokens of the same type
        original_match_score=.5): ## If the token is a spacer, we want to match the original token
    """
    Performs Needleman-Wunsch alignment on two lists of tokens, with a modified mismatch score
    based on the length of the longest common substring.
    """
    text1.clear_alignment()
    text2.clear_alignment()
    s1_tokens = text1.tokens
    s2_tokens = text2.tokens
    n = len(s1_tokens)
    m = len(s2_tokens)

    # Initialize score matrix and traceback matrix
    score_matrix = [[0] * (m + 1) for _ in range(n + 1)]
    traceback_matrix = [[''] * (m + 1) for _ in range(n + 1)]

    # Initialize first row and column for gaps
    for i in range(n + 1):
        score_matrix[i][0] = gap_score * i
        if i > 0:
            traceback_matrix[i][0] = 'U'
    for j in range(m + 1):
        score_matrix[0][j] = gap_score * j
        if j > 0:
            traceback_matrix[0][j] = 'L'

    # Fill in the score matrix and traceback matrix
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            token1 = s1_tokens[i - 1]
            token2 = s2_tokens[j - 1]
            if token1.text == token2.text:
                match = score_matrix[i - 1][j - 1] + match_score
            else:
                ## If it's a spacer, ideally we want to align to the original token for easier debugging
                original_match = 0
                if isinstance(token1.original, bool):
                    print(token1.original, type(token1))

                if token1.original is not None:
                    to_match1 = token1.original
                    text1 = token1.original.text                    
                    if text1 == token2.text:
                        original_match = original_match_score
                    if isinstance(to_match1, type(token2)):
                        original_match += type_match_score
                else:
                    to_match1 = token1
                    text1 = token1.text

                # Calculate mismatch score based on substring length
                lcs = longest_common_substring(text1, token2.text)
                max_len = max(len(to_match1.text), len(token2.text))
                
                # proportional scaling - the longer the substring, the smaller the penalty
                mismatch_score_adjusted = mismatch_score + (len(lcs) / max_len) * substring_match_score
                if isinstance(token1, type(token2)) and max_len > 1:
                    mismatch_score_adjusted += type_match_score

                ## Additional score for matching types of tokens

                match = score_matrix[i - 1][j - 1] + mismatch_score_adjusted + original_match

            delete = score_matrix[i - 1][j] + gap_score
            insert = score_matrix[i][j - 1] + gap_score

            max_score = max(match, delete, insert)
            # print(f"match: {match}, delete: {delete}, insert: {insert}, max_score: {max_score}")
            score_matrix[i][j] = max_score


            if max_score == match:
                traceback_matrix[i][j] += 'D'
            if max_score == delete:
                traceback_matrix[i][j] += 'U'
            if max_score == insert:
                traceback_matrix[i][j] += 'L'

    return score_matrix, traceback_matrix


def get_alignment_and_visualization_words(text1: Text, text2: Text, score_matrix, traceback_matrix, base_alignment=None):
    """
    Traceback to get the alignment for words, create visualization strings, and colorize mismatches,
    and equalize the length of aligned words by inserting Spacer objects.
    """
    n = len(text1.tokens)
    m = len(text2.tokens)
    aligned_text1 = Text()
    aligned_text2 = Text()
    i = n
    j = m

    while i >= 0 or j >= 0:
        trace = traceback_matrix[i][j]
        token1 = text1.tokens[i - 1] if i > 0 else text1.tokens[0]
        token2 = text2.tokens[j - 1] if j > 0 else text2.tokens[0]

        if 'D' in trace and i > 0 and j > 0:
            aligned_text1.insert(0, token1)
            aligned_text2.insert(0, token2)
            i -= 1
            j -= 1
        elif 'U' in trace and i > 0:
            ## Check if the token2 is a spacer already
            if isinstance(token2, Spacer):
                spacer = token2
                spacer.alignment_spaces = len(token1)
            else:
                spacer = Spacer(text='', aligned=True, alignment_spaces=len(token1)) 
            aligned_text1.insert(0, token1)
            aligned_text2.insert(0, spacer)  # Using Spacer instead of "@" string
            i -= 1
        elif 'L' in trace and j > 0:
            ## Check if the token1 is a spacer already
            if isinstance(token1, Spacer):
                spacer = token1
                spacer.alignment_spaces = len(token2)
            else:
                spacer = Spacer(text='', aligned=True, alignment_spaces=len(token2))
            aligned_text1.insert(0, spacer)  # Using Spacer instead of "@" string
            aligned_text2.insert(0, token2)
            j -= 1
        else:
            break
    
    for w1, w2 in zip(aligned_text1.tokens, aligned_text2.tokens):
        if w1.text != w2.text:
            max_len = max(len(w1), len(w2))
            w1.alignment_spaces = max_len - len(w1)
            w2.alignment_spaces = max_len - len(w2)
            if isinstance(w1, Spacer):
                color = 'b'
            elif isinstance(w2, Spacer):
                color = 'p'
            else:
                color = 'r'

            w1.aligned = True
            w2.aligned = True
            w1.set_color(color)
            w2.set_color(color)

    return aligned_text1, aligned_text2
