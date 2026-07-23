"""Split book text into natural reading blocks."""



from __future__ import annotations



import re



# Target words per block — used in Settings

BLOCK_WORD_OPTIONS = [35, 55, 75, 100, 130, 170, 220, 280]



_ABBREV_PATTERN = re.compile(

    r"\b(?:"

    r"Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc|Inc|Ltd|Vol|Fig|No|Ref|approx|dept|est|govt"

    r"|i\.e|e\.g|U\.S|U\.K|Ph\.D|M\.D|B\.A|M\.A"

    r")\.\s*",

    re.IGNORECASE,

)





class TextSplitter:

    SENTENCE_END = re.compile(

        r'(?<=[.!?…])\s+(?=[A-Z0-9"\u201c\u2018(\[]|\d)'

    )



    def __init__(self, target_words: int = 55) -> None:

        self.configure(target_words)



    def configure(self, target_words: int) -> None:

        target = max(20, min(350, target_words))

        self.TARGET_WORDS = target

        self.MIN_WORDS = max(15, int(target * 0.55))

        self.MAX_WORDS = int(target * 1.45)

        self.MERGE_THRESHOLD = max(8, self.MIN_WORDS // 2)



    def split_into_blocks(self, text: str, chapter: str = "") -> list[tuple[str, str]]:

        text = self._normalize(text)

        if not text.strip():

            return []



        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

        blocks: list[tuple[str, str]] = []



        for paragraph in paragraphs:

            blocks.extend(self._split_paragraph(paragraph, chapter))



        return self._merge_short_blocks(blocks)



    def _normalize(self, text: str) -> str:

        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # PDF/EPUB hyphenation at line break: "some-\nthing" -> "something"

        text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)

        # Soft line breaks inside a paragraph become spaces

        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

        text = re.sub(r"[ \t]+", " ", text)

        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()



    def _split_sentences(self, paragraph: str) -> list[str]:

        protected = paragraph

        placeholders: list[str] = []



        def _protect(match: re.Match[str]) -> str:

            placeholders.append(match.group(0))

            return f"__ABB{len(placeholders) - 1}__"



        protected = _ABBREV_PATTERN.sub(_protect, protected)

        parts = self.SENTENCE_END.split(protected)

        sentences: list[str] = []

        for part in parts:

            part = part.strip()

            if not part:

                continue

            for idx, original in enumerate(placeholders):

                part = part.replace(f"__ABB{idx}__", original)

            sentences.append(part)

        return sentences if sentences else [paragraph.strip()]



    def _merge_orphan_fragments(self, sentences: list[str]) -> list[str]:

        """Join 1–2 word fragments caused by bad OCR/PDF line breaks."""

        if not sentences:

            return []



        merged: list[str] = []

        pending = ""



        for sentence in sentences:

            sentence = sentence.strip()

            if not sentence:

                continue



            word_count = len(sentence.split())

            ends_sentence = bool(re.search(r"[.!?…]$", sentence))



            if pending:

                sentence = f"{pending} {sentence}".strip()

                pending = ""

                word_count = len(sentence.split())

                ends_sentence = bool(re.search(r"[.!?…]$", sentence))



            if word_count <= 2 and not ends_sentence:

                pending = sentence

                continue



            if word_count <= 2 and merged:

                merged[-1] = f"{merged[-1]} {sentence}".strip()

                continue



            merged.append(sentence)



        if pending:

            if merged:

                merged[-1] = f"{merged[-1]} {pending}".strip()

            else:

                merged.append(pending)



        return merged



    def _split_paragraph(

        self, paragraph: str, chapter: str

    ) -> list[tuple[str, str]]:

        sentences = self._merge_orphan_fragments(self._split_sentences(paragraph))

        if not sentences:

            return []



        blocks: list[tuple[str, str]] = []

        current: list[str] = []

        current_words = 0



        for sentence in sentences:

            word_count = len(sentence.split())

            if word_count == 0:

                continue



            if current_words + word_count > self.MAX_WORDS and current:

                blocks.append((" ".join(current), chapter))

                current = [sentence]

                current_words = word_count

            else:

                current.append(sentence)

                current_words += word_count



                if current_words >= self.TARGET_WORDS:

                    blocks.append((" ".join(current), chapter))

                    current = []

                    current_words = 0



        if current:

            block_text = " ".join(current)

            word_count = len(block_text.split())

            if word_count < self.MIN_WORDS and blocks:

                prev_text, prev_chapter = blocks[-1]

                combined = f"{prev_text} {block_text}"

                if len(combined.split()) <= self.MAX_WORDS:

                    blocks[-1] = (combined, prev_chapter)

                else:

                    blocks.append((block_text, chapter))

            else:

                blocks.append((block_text, chapter))



        return blocks



    def _merge_short_blocks(

        self, blocks: list[tuple[str, str]]

    ) -> list[tuple[str, str]]:

        if not blocks:

            return []



        merged: list[tuple[str, str]] = [blocks[0]]

        for text, chapter in blocks[1:]:

            word_count = len(text.split())

            if word_count < self.MERGE_THRESHOLD:

                prev_text, prev_chapter = merged[-1]

                combined = f"{prev_text} {text}".strip()

                if len(combined.split()) <= self.MAX_WORDS:

                    merged[-1] = (combined, prev_chapter)

                    continue

            merged.append((text, chapter))



        if len(merged) >= 2:

            last_text, last_chapter = merged[-1]

            if len(last_text.split()) < self.MERGE_THRESHOLD:

                prev_text, prev_chapter = merged[-2]

                combined = f"{prev_text} {last_text}".strip()

                if len(combined.split()) <= self.MAX_WORDS:

                    merged[-2] = (combined, prev_chapter)

                    merged.pop()



        return merged



    def count_words(self, text: str) -> int:

        return len(text.split())

