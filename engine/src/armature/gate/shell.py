"""A shell command line read as the simple commands it runs, so the hook
can find a git merge, commit or push wherever it sits: after `&&`, `;`, a
pipe or a newline, in a `( … )` subshell, inside `$( … )` or backticks,
quoted or not. Bash and PowerShell are read alike, but for their escape
character (`\\` against the backtick), their comments and here-documents.

    commands("cd arm && git merge \\"$(git branch --show-current)\\"")
    -> [["cd", "arm"], ["git", "branch", "--show-current"],
        ["git", "merge", <unknown>]]

A word is its text with the quoting removed. A word that holds a
substitution or a variable is `UNKNOWN`-marked: its value is not known
until the shell runs. A substitution's commands come before the command
whose word holds them, since they run first. Redirections and their
targets are dropped, and a here-document's body is never read as
commands: a commit message may name a merge.
"""

import re

# Marks a word whose value is known only when the shell runs it.
UNKNOWN = "\0"
SEPARATORS = ";&|\n"
OPERATORS = SEPARATORS + "()<>"
HEREDOC = re.compile(r"(-?)[ \t]*(['\"]?)([^\s'\";&|()<>]+)\2")
PS_HERESTRING = re.compile(r"@(['\"])[ \t]*\r?\n.*?\r?\n\1@", re.S)


def commands(text, shell="bash"):
    """Each simple command `text` runs, as a list of its words."""
    if shell == "powershell":
        text = PS_HERESTRING.sub("''", text)
    lexer = _Lexer(text, shell)
    lexer.run()
    return lexer.out


class _Lexer:
    def __init__(self, text, shell, at=0, closing=None):
        self.text, self.shell, self.at = text, shell, at
        self.escape = "`" if shell == "powershell" else "\\"
        self.closing = closing        # the `)` that ends a substitution
        self.out, self.words = [], []
        self.word = None              # the word being read, or None
        self.subs = []                # commands of the word's substitutions
        self.redirect = False         # the next word is a redirect target
        self.heredocs = []            # (delimiter, strip tabs) pending
        self.depth = 0

    # --- words and commands ---------------------------------------------
    def add(self, text):
        self.word = (self.word or "") + text

    def end_word(self):
        if self.word is None:
            return
        if self.redirect:
            self.redirect = False
        elif self.word in ("{", "}") and not self.subs:
            self.end_command()
        else:
            self.words.append(self.word)
        self.word = None

    def end_command(self):
        self.end_word()
        self.redirect = False
        self.out += self.subs
        self.subs = []
        if self.words:
            self.out.append(self.words)
        self.words = []

    # --- the reader -----------------------------------------------------
    def run(self):
        text = self.text
        while self.at < len(text):
            c = text[self.at]
            if c in " \t\r":
                self.end_word()
                self.at += 1
            elif c == "\n":
                self.end_command()
                self.at += 1
                self.skip_heredocs()
            elif c == "#" and self.word is None:
                self.at = _line_end(text, self.at)
            elif (c == "<" and self.shell == "powershell"
                  and text.startswith("<#", self.at)):
                end = text.find("#>", self.at + 2)
                self.at = len(text) if end < 0 else end + 2
            elif c == self.escape:
                self.escaped()
            elif c == "'":
                self.single()
            elif c == '"':
                self.double()
            elif text.startswith("$(", self.at) or (
                    self.shell == "powershell"
                    and text.startswith("@(", self.at)):
                self.substitution(self.at + 2)
            elif c == "`":                    # bash: an old substitution
                self.backticks()
            elif c == "$":
                self.add(UNKNOWN)
                self.at += 1
            elif c in OPERATORS:
                if c == ")" and self.depth == 0 and self.closing:
                    self.end_command()
                    self.at += 1
                    return
                self.operator(c)
            else:
                self.add(c)
                self.at += 1
        self.end_command()

    def escaped(self):
        nxt = self.text[self.at + 1:self.at + 2]
        self.at += 2
        if nxt == "\n":
            return                            # a line continued
        self.add(nxt)

    def single(self):
        end = self.text.find("'", self.at + 1)
        end = len(self.text) if end < 0 else end
        self.add(self.text[self.at + 1:end])
        self.at = end + 1
        if (self.shell == "powershell"
                and self.text.startswith("'", self.at)):   # '' is a quote
            self.add("'")

    def double(self):
        self.add("")
        self.at += 1
        text = self.text
        while self.at < len(text) and text[self.at] != '"':
            c = text[self.at]
            if c == self.escape:
                self.escaped()
            elif text.startswith("$(", self.at):
                self.substitution(self.at + 2)
            elif c == "`" and self.shell == "bash":
                self.backticks()
            elif c == "$" and text[self.at + 1:self.at + 2].strip():
                self.add(UNKNOWN)
                self.at += 1
            else:
                self.add(c)
                self.at += 1
        self.at += 1

    def substitution(self, start):
        inner = _Lexer(self.text, self.shell, start, closing=")")
        inner.run()
        self.subs += inner.out
        self.add(UNKNOWN)
        self.at = inner.at

    def backticks(self):
        end = self.text.find("`", self.at + 1)
        end = len(self.text) if end < 0 else end
        self.subs += commands(self.text[self.at + 1:end], self.shell)
        self.add(UNKNOWN)
        self.at = end + 1

    def operator(self, c):
        text = self.text
        if c in "<>" or (c == "&" and text.startswith("&>", self.at)):
            if self.word is not None and self.word.isdigit():
                self.word = None              # 2>&1: the 2 is a descriptor
            self.end_word()
            if text.startswith("<<", self.at) and not text.startswith(
                    "<<<", self.at):
                match = HEREDOC.match(text, self.at + 2)
                if match:
                    self.heredocs.append((match[3], bool(match[1])))
                    self.at = match.end()
                    return
            op = re.match(r"&?[<>]+[&|]?", text[self.at:])[0]
            self.at += len(op)
            self.redirect = True              # its target is no argument
            return
        self.end_command()
        if c == "(":
            self.depth += 1
        elif c == ")":
            self.depth = max(0, self.depth - 1)
        self.at += 1

    def skip_heredocs(self):
        """Skip each pending here-document's body, ending at its
        delimiter's own line."""
        text = self.text
        for delimiter, tabs in self.heredocs:
            while self.at < len(text):
                end = _line_end(text, self.at)
                line = text[self.at:end].rstrip("\r")
                self.at = min(end + 1, len(text))
                if (line.lstrip("\t") if tabs else line) == delimiter:
                    break
        self.heredocs = []


def _line_end(text, at):
    end = text.find("\n", at)
    return len(text) if end < 0 else end
