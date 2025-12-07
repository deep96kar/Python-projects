import sys
import os
import webbrowser
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime

# parent folder path add
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from SpeechToText_Python.SpeechToText_Python import *
from Data.Web_Data import websites

# input.txt er location (ei file-er same folder e thakbe)
INPUT_FILE = Path(__file__).resolve().parent / "input.txt"


def normalize_word(word: str) -> str:
    """Clean user input like 'Youtube.com', 'WWW.GOOGLE.COM', etc."""
    w = word.lower().strip()

    # Remove common punctuation
    w = w.strip(",.!?/:\\|")

    # Remove protocol if spoken as URL
    for prefix in ("http://", "https://"):
        if w.startswith(prefix):
            w = w[len(prefix):]

    # Remove 'www.'
    if w.startswith("www."):
        w = w[4:]

    # Remove common domain endings
    for suffix in (".com", ".in", ".org", ".net"):
        if w.endswith(suffix):
            w = w[: -len(suffix)]

    return w


def log_to_file(message: str, status: bool = None) -> None:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(INPUT_FILE, "a", encoding="utf-8") as f:
            if status is not None:
                f.write(f"{timestamp} | DEEP: {message} | {status}\n")
            else:
                f.write(f"{timestamp} |  DEEP: {message}\n")
    except Exception as e:
        print(f"[LOG ERROR] There is a problem writing to input.txt: {e}")


def similarity(a: str, b: str) -> float:
    """Return similarity ratio between words"""
    return SequenceMatcher(None, a, b).ratio()


def get_candidates(name: str, min_score: float = 0.82, max_results: int = 5):
    scores = []
    for key in websites.keys():
        score = similarity(name, key)
        if score >= min_score:
            scores.append((key, score))

    # score desc sort
    scores.sort(key=lambda x: x[1], reverse=True)

    return scores[:max_results]


def openweb(text: str) -> None:
    """
    text: full sentence from speech or typing, e.g.
      'open google and youtube'
      'youtube.com khulo'
    """

    # ---- 2) website gula ber kore open kori ----
    words = text.split()
    normalized_words = [normalize_word(w) for w in words]

    urls_to_open = []
    opened_urls = set()

    for original, name in zip(words, normalized_words):

        # 1) Exact match hole direct open list e
        if name in websites:
            url = websites[name]
            if url not in opened_urls:
                urls_to_open.append(url)
                opened_urls.add(url)
            continue

        # 2) Similar website gula ber kori (onek match thakle o)
        candidates = get_candidates(name)

        if not candidates:
            # kono reasonable match nai → skip
            continue

        if len(candidates) == 1:
            # sudhu 1 ta strong match → simple confirm
            corrected, score = candidates[0]
            print(
                f"Did you mean '{corrected}' instead of '{original}'? (y/n): ",
                end=""
            )
            ans = input("").strip().lower()

            if ans == "y":
                url = websites[corrected]
                if url not in opened_urls:
                    urls_to_open.append(url)
                    opened_urls.add(url)

        else:
            # onek gulo strong match → list dekhabo
            print(f"Multiple matches found for '{original}':")
            for i, (cand, score) in enumerate(candidates, start=1):
                print(f"  {i}. {cand}  ({score*100:.0f}% match)")

            choice = input(
                "Enter number to open, 'a' for all, or 'n' to skip: "
            ).strip().lower()

            if choice == "n" or choice == "":
                # skip
                continue
            elif choice == "a":
                # sob open
                for cand, _ in candidates:
                    url = websites[cand]
                    if url not in opened_urls:
                        urls_to_open.append(url)
                        opened_urls.add(url)
            elif choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(candidates):
                    cand, _ = candidates[idx - 1]
                    url = websites[cand]
                    if url not in opened_urls:
                        urls_to_open.append(url)
                        opened_urls.add(url)
                else:
                    print("Invalid choice, skipping.")
                    continue
            else:
                print("Invalid choice, skipping.")
                continue

    if urls_to_open:
        for url in urls_to_open:
            webbrowser.open(url)
        print(f"Opened {len(urls_to_open)} website(s).")
        log_to_file(text, True)
    else:
        print("No valid website names found.")
        log_to_file(text, False)


def main():
    while True:
        web_input = input("web name (or 'exit'): ").strip()

        if web_input.lower() in {"exit", "quit", "q"}:
            print("Exiting...")
            break

        if not web_input:
            continue

        # ekhanei openweb call korle file-o update hobe + site o open hobe
        openweb(web_input)


if __name__ == "__main__":
    main()
    # speech theke use korte chaile:
    # text = Speech_To_Text_Python()
    # openweb(text)
