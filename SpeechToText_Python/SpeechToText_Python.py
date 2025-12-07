import re
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

import speech_recognition as sr
from googletrans import Translator
from colorama import Fore, Style, init

init(autoreset=True)

# ================== CONFIG ================== #

translator = Translator()
OUTPUT_FILE = Path(__file__).resolve().parent / "input.txt"

MIC_PREFERRED_KEYWORDS = ["wo mic", "phone", "usb", "bluetooth", "external", "mobile"]

SR_SETTINGS = {
    "dynamic_energy_threshold": True,
    "energy_threshold": 0,
    "dynamic_energy_adjustment_damping": 0.15,
    "dynamic_energy_ratio": 1.8,
    "pause_threshold": 0.38,
    "phrase_threshold": 0.18,
    "non_speaking_duration": 0.35,
    "operation_timeout": None,
}

# ================== TRANSLATION UTILS ================== #

def translate_to_english(text: str, src_lang: str) -> str:
    """Translate given text from src_lang → English. Fallback to original on error."""
    try:
        result = translator.translate(text, src=src_lang, dest="en")
        return result.text
    except Exception as e:
        print(Fore.RED + f"Translation error ({src_lang} → en): {e}")
        return text


def detect_lang_code(text: str) -> str:
    """Return detected language code, or '' on error."""
    try:
        detection = translator.detect(text)
        return detection.lang
    except Exception as e:
        print(Fore.RED + f"Language detection error: {e}")
        return ""


def append_to_input_file(text: str) -> None:
    """Append recognized text to the shared input file with timestamp and DEEP: prefix."""
    try:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with OUTPUT_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{timestamp} | DEEP: {text}\n")
    except Exception as e:
        print(Fore.RED + f"File write error: {e}")



# ================== RECOGNITION UTILS ================== #

def recognize_with_confidence(
    recognizer: sr.Recognizer, audio: sr.AudioData
) -> Tuple[str, Optional[float]]:
    """
    Get transcript plus a best-effort confidence score from Google.
    Returns: (transcript, confidence or None)
    """
    try:
        result = recognizer.recognize_google(audio, show_all=True)
    except Exception:
        return "", None

    if not isinstance(result, dict) or "alternative" not in result:
        return "", None

    alts = result.get("alternative", [])
    if not alts:
        return "", None

    best = max(alts, key=lambda a: a.get("confidence", 0), default=alts[0])
    transcript = best.get("transcript", "").strip()
    confidence = best.get("confidence")
    return transcript, confidence


# ================== NORMALIZATION (OPERATORS + EXTENSIONS) ================== #

# General punctuation / operators (including #, $, &)
_PUNCT_PATTERNS = [
    # Special ones you asked for
    (re.compile(r"\b(hash|pound|number sign)\b", re.I), "#"),
    (re.compile(r"\b(dollar|dollar sign)\b", re.I), "$"),
    (re.compile(r"\b(ampersand|and sign)\b", re.I), "&"),

    # Rest
    (re.compile(r"\b(dot|period|full stop)\b", re.I), "."),
    (re.compile(r"\b(comma)\b", re.I), ","),
    (re.compile(r"\b(semicolon)\b", re.I), ";"),
    (re.compile(r"\b(colon)\b", re.I), ":"),
    (re.compile(r"\b(underscore|under score)\b", re.I), "_"),
    (re.compile(r"\b(dash|hyphen|minus)\b", re.I), "-"),
    (re.compile(r"\b(plus|add|plus sign)\b", re.I), "+"),
    (re.compile(r"\b(slash|forward slash)\b", re.I), "/"),
    (re.compile(r"\b(backslash|back slash)\b", re.I), r"\\"),
    (re.compile(r"\b(star|asterisk)\b", re.I), "*"),
    (re.compile(r"\b(percent|percentage)\b", re.I), "%"),
    (re.compile(r"\b(equal|equals|equal to)\b", re.I), "="),
    (re.compile(r"\b(greater than)\b", re.I), ">"),
    (re.compile(r"\b(less than)\b", re.I), "<"),
    (re.compile(r"\b(pipe|vertical bar)\b", re.I), "|"),
    (re.compile(r"\b(caret)\b", re.I), "^"),
    (re.compile(r"\b(at|at the rate)\b", re.I), "@"),
    (re.compile(r"\b(exclamation|bang|exclamation mark)\b", re.I), "!"),
    (re.compile(r"\b(question mark|question)\b", re.I), "?"),
    (re.compile(r"\b(quote|double quote)\b", re.I), '"'),
    (re.compile(r"\b(single quote|apostrophe)\b", re.I), "'"),
    (re.compile(r"\b(open parenthesis|open bracket|left parenthesis)\b", re.I), "("),
    (re.compile(r"\b(close parenthesis|close bracket|right parenthesis)\b", re.I), ")"),
    (re.compile(r"\b(open brace|left brace)\b", re.I), "{"),
    (re.compile(r"\b(close brace|right brace)\b", re.I), "}"),
    (re.compile(r"\b(open square bracket|left square bracket)\b", re.I), r"["),
    (re.compile(r"\b(close square bracket|right square bracket)\b", re.I), r"]"),

    # Extras (optional)
    (re.compile(r"\b(space|blank)\b", re.I), " "),
    (re.compile(r"\b(new line|newline)\b", re.I), "\n"),
]

# Spoken extension variants → .ext
# You can add more extensions here easily
_EXTENSION_VARIANTS = {
    "txt": ["t x t", "txt"],
    "py":  ["p y", "py"],
    "c":   ["c"],
    "cpp": ["c p p", "cpp", "c plus plus"],
    # "java": ["java"],
    # "js":   ["j s", "js", "javascript"],
    # "html": ["h t m l", "html"],
    # "css":  ["c s s", "css"],
}

_DOT_EXT_PATTERNS = []

# Prebuild regex: "dot t x t", "dot txt", "dot p y", "dot c", "dot c p p", ...
for ext, variants in _EXTENSION_VARIANTS.items():
    for variant in variants:
        # "t x t" -> r"t\s*x\s*t"
        parts = variant.split()
        variant_regex = r"\s*".join(map(re.escape, parts))
        pattern = re.compile(r"\bdot\s+" + variant_regex + r"\b", re.I)
        _DOT_EXT_PATTERNS.append((pattern, f".{ext}"))


def normalize_pronounced_punctuation(text: str) -> str:
    """Turn spoken operators/punctuation and 'dot extension' into symbols."""
    normalized = text

    # 1) First handle .txt / .py / .c / .cpp etc.
    for pattern, repl in _DOT_EXT_PATTERNS:
        normalized = pattern.sub(repl, normalized)

    # 2) General punctuation words → symbols
    for pattern, repl in _PUNCT_PATTERNS:
        normalized = pattern.sub(repl, normalized)

    # 3) Tighten spaces around common symbols so filenames look right
    normalized = re.sub(r"\s*([/\\\.\-\+\*%=&\|\^#@!\?,:;])\s*", r"\1", normalized)

    # 4) Tighten around brackets/braces
    normalized = re.sub(r"\s*\(\s*", "(", normalized)
    normalized = re.sub(r"\s*\)\s*", ")", normalized)
    normalized = re.sub(r"\s*\[\s*", "[", normalized)
    normalized = re.sub(r"\s*\]\s*", "]", normalized)
    normalized = re.sub(r"\s*\{\s*", "{", normalized)
    normalized = re.sub(r"\s*\}\s*", "}", normalized)

    # 5) Collapse spaces
    normalized = re.sub(r"[ \t]+", " ", normalized)


    # Step:  tighten spaces around operators BUT keep one real space on both sides
    normalized = re.sub(r"\s*([+\-*/%=&|^<>])\s*", r" \1 ", normalized)

    # Remove multiple spaces
    normalized = re.sub(r"\s+", " ", normalized)

    # Remove space before punctuation like . , ? !
    normalized = re.sub(r"\s*([.,?!])", r"\1", normalized)

    # Remove extra spaces at ends
    normalized = normalized.strip()

    return normalized.strip()


# ================== MICROPHONE HANDLING ================== #

def choose_microphone(recognizer: sr.Recognizer) -> Optional[int]:
    """Pick the best available working microphone based on preferred keywords."""
    try:
        mic_list = sr.Microphone.list_microphone_names()
    except Exception as e:
        print(Fore.RED + f"Error listing microphones: {e}")
        return None

    mic_index = None

    for index, name in enumerate(mic_list):
        name_lower = name.lower()
        if any(keyword in name_lower for keyword in MIC_PREFERRED_KEYWORDS):
            try:
                # Quick test if mic actually works
                with sr.Microphone(device_index=index) as test_source:
                    recognizer.adjust_for_ambient_noise(test_source, duration=0.3)
                mic_index = index
                print(Fore.GREEN + f"Using microphone: {name}")
                break
            except Exception:
                print(Fore.YELLOW + f"Skipping inactive mic: {name}")
                continue

    if mic_index is None:
        print(Fore.YELLOW + "Using default microphone")
    return mic_index


def recalibrate_noise(
    recognizer: sr.Recognizer,
    source: sr.AudioSource,
    miss_streak: int
) -> int:
    """Re-calibrate to ambient noise after several misses."""
    if miss_streak < 4:
        return miss_streak

    print(Fore.YELLOW + "Re-calibrating to ambient noise (quiet please)...")
    recognizer.adjust_for_ambient_noise(source, duration=0.8)
    recognizer.dynamic_energy_ratio = min(recognizer.dynamic_energy_ratio + 0.1, 2.2)
    print(
        Fore.GREEN
        + f"New energy threshold: {recognizer.energy_threshold:.1f} | "
          f"ratio: {recognizer.dynamic_energy_ratio:.2f}"
    )
    return 0


# ================== MAIN LOOP ================== #

def Speech_To_Text_Python() -> None:
    recognizer = sr.Recognizer()

    # Apply SR tuning
    for k, v in SR_SETTINGS.items():
        setattr(recognizer, k, v)

    mic_index = choose_microphone(recognizer)

    try:
        with sr.Microphone(device_index=mic_index, sample_rate=16000, chunk_size=1024) as source:
            print(Fore.YELLOW + "Calibrating microphone... Please be silent.")
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
            print(Fore.GREEN + f"Calibrated energy threshold: {recognizer.energy_threshold:.1f}")
            print(Fore.GREEN + "Listening... (Ctrl + C to stop)\n")

            miss_streak = 0
            last_written: Optional[str] = None

            while True:
                try:
                    print(Fore.GREEN + "Listening...", end="", flush=True)
                    audio = recognizer.listen(source, timeout=None, phrase_time_limit=4)

                    print("\r" + Fore.LIGHTBLACK_EX + "Recognizing....", end="", flush=True)
                    raw_text, confidence = recognize_with_confidence(recognizer, audio)
                    print("\r" + " " * 50 + "\r", end="", flush=True)  # Clear the line

                    if not raw_text:
                        miss_streak += 1
                        print(Fore.YELLOW + "No speech detected or could not recognize.")
                        miss_streak = recalibrate_noise(recognizer, source, miss_streak)
                        continue

                    clean_text = " ".join(raw_text.split())
                    miss_streak = 0  # reset on success

                    # Basic quality warnings
                    warning = ""
                    if len(clean_text.split()) == 1 and len(clean_text) < 3:
                        warning += " [⚠️ Very short - might be unclear]"
                    if clean_text.isupper():
                        warning += " [⚠️ All caps - check audio quality]"
                    if confidence is not None:
                        warning += f" [conf {confidence:.2f}]"

                    print(Fore.CYAN + f"RAW: {clean_text}" + Fore.YELLOW + warning)

                    # Detect language + translate to English if needed
                    lang = detect_lang_code(clean_text)
                    text_for_file = clean_text

                    if lang == "hi":
                        trans_text = translate_to_english(clean_text, "hi")
                        text_for_file = trans_text
                        print(Fore.BLUE + "DEEP (Hindi → Eng): " + trans_text)

                    elif lang == "bn":
                        trans_text = translate_to_english(clean_text, "bn")
                        text_for_file = trans_text
                        print(Fore.BLUE + "DEEP (Bengali → Eng): " + trans_text)

                    elif lang == "en":
                        print(Fore.BLUE + "DEEP (English): " + clean_text)
                    else:
                        print(Fore.BLUE + "DEEP (No translation): " + clean_text)

                    # Normalize punctuation / operators / extensions
                    before_norm = text_for_file
                    text_for_file = normalize_pronounced_punctuation(text_for_file)
                    print(Fore.MAGENTA + f"NORM: {before_norm}  -->  {text_for_file}")

                    # Skip writing extremely low-confidence guesses
                    if confidence is not None and confidence < 0.3:
                        print(Fore.YELLOW + "Skipping write (low confidence)")
                        continue

                    # Skip duplicates
                    if text_for_file and text_for_file == last_written:
                        print(Fore.YELLOW + "Duplicate text skipped")
                        continue

                    append_to_input_file(text_for_file)
                    last_written = text_for_file

                except sr.UnknownValueError:
                    miss_streak += 1
                    print("\r" + " " * 50 + "\r", end="", flush=True)  # Clear the line
                    print(Fore.YELLOW + "Could not understand audio.")
                    miss_streak = recalibrate_noise(recognizer, source, miss_streak)

                except KeyboardInterrupt:
                    print("\n" + Fore.RED + "Exiting on user request (Ctrl+C). Bye!")
                    break

                finally:
                    print("", end="", flush=True)

    except OSError as e:
        print(Fore.RED + f"Microphone Error: {e}")
        print(
            Fore.YELLOW
            + "Try: 1) Check microphone is connected, 2) Allow microphone access in Windows Settings"
        )
    except Exception as e:
        print(Fore.RED + f"Error: {e}")


if __name__ == "__main__":
    Speech_To_Text_Python()
