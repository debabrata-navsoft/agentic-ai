from collections import Counter
from pathlib import Path


def load_text(path):
    return Path(path).read_text(encoding="utf-8")


def char_stats(text):
    counts = Counter(text)
    return counts


def word_stats(text):
    words = text.lower().split()
    return Counter(words)


def main():
    text = load_text("data/shakespeare.txt")
    print("Total characters:", len(text))

    chars = char_stats(text)
    print("Unique characters (vocabulary size):", len(chars))
    print("Vocabulary:", "".join(sorted(chars)))

    words = word_stats(text)
    print("Total words:", sum(words.values()))
    print("Unique words:", len(words))
    print("10 most common words:")
    for word, count in words.most_common(10):
        print(f"  {word!r}: {count}")


if __name__ == "__main__":
    main()
