#!/usr/bin/env python3
"""PDF Tool: split a PDF into single pages, combine multiple PDFs, or rotate a PDF.

Usage:
    pip install pypdf
    python split_pdf.py
"""

import sys
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PdfReadError
except ImportError:
    print("The 'pypdf' package is required. Install it with:  pip install pypdf")
    sys.exit(1)


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------

def validate_file(path_str: str) -> Path:
    """Return a valid PDF Path or raise a ValueError with a clear message."""
    # Remove surrounding quotes (common when dragging a file into the terminal)
    path = Path(path_str.strip().strip('"').strip("'")).expanduser()

    if not path.exists():
        raise ValueError(f"The file '{path}' does not exist.")
    if not path.is_file():
        raise ValueError(f"'{path}' is not a file.")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"'{path.name}' is not a PDF file (extension: '{path.suffix or 'none'}').")
    return path


def open_pdf(pdf_path: Path) -> PdfReader:
    """Open a PDF and make sure it is readable, unlocked and not empty."""
    try:
        reader = PdfReader(str(pdf_path))
    except PdfReadError:
        raise ValueError(f"'{pdf_path.name}' is not a valid PDF or is corrupted.")

    if reader.is_encrypted:
        # Try an empty password first (many PDFs are "encrypted" without a password)
        if not reader.decrypt(""):
            raise ValueError(f"'{pdf_path.name}' is password-protected and cannot be processed.")

    if len(reader.pages) == 0:
        raise ValueError(f"'{pdf_path.name}' contains no pages.")
    return reader


# --------------------------------------------------------------------------
# Split mode
# --------------------------------------------------------------------------

def split_pdf(pdf_path: Path) -> Path:
    """Split the PDF into single pages. Returns the output folder."""
    reader = open_pdf(pdf_path)
    total_pages = len(reader.pages)

    # Output goes into a folder next to the original file
    output_dir = pdf_path.parent / f"{pdf_path.stem}_pages"
    output_dir.mkdir(exist_ok=True)

    padding = len(str(total_pages))  # page_01, page_02 ... keeps files sorted properly

    for index, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        out_file = output_dir / f"{pdf_path.stem}_page_{str(index).zfill(padding)}.pdf"
        with open(out_file, "wb") as f:
            writer.write(f)

    print(f"Split {total_pages} page(s) into: {output_dir}")
    return output_dir


def split_mode() -> None:
    print("\n--- Split mode ---")
    while True:
        user_input = input("\nWhich PDF file would you like to split? (or 'q' to go back): ").strip()

        if user_input.lower() in {"q", "quit", "exit"}:
            return
        if not user_input:
            print("Error: please enter a file name.")
            continue

        try:
            split_pdf(validate_file(user_input))
            return
        except ValueError as err:
            print(f"Error: {err}")
        except PermissionError:
            print("Error: permission denied. Check the file/folder permissions.")
        except OSError as err:
            print(f"Error: could not read or write files ({err}).")
        except Exception as err:  # last-resort safety net
            print(f"Unexpected error: {err}")


# --------------------------------------------------------------------------
# Combine mode
# --------------------------------------------------------------------------

def ask_output_path(default_dir: Path, inputs: list[Path]) -> Path | None:
    """Ask for the output file name. Returns None if the user cancels."""
    while True:
        name = input("\nName for the combined PDF [combined.pdf] (or 'q' to cancel): ").strip()
        if name.lower() in {"q", "quit", "cancel"}:
            return None

        name = name.strip('"').strip("'") or "combined.pdf"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"

        out_path = Path(name).expanduser()
        if not out_path.is_absolute():
            out_path = default_dir / out_path

        # Never overwrite one of the files we are reading from
        if any(out_path.resolve() == p.resolve() for p in inputs):
            print("Error: the output name matches one of the input files. Choose another name.")
            continue

        if out_path.exists():
            answer = input(f"'{out_path.name}' already exists. Overwrite? (y/n): ").strip().lower()
            if answer not in {"y", "yes"}:
                continue
        return out_path


def combine_mode() -> None:
    print("\n--- Combine mode ---")
    print("Enter PDF file names one at a time, in the order they should appear.")
    print("Commands:  'done' = finish and combine   'undo' = remove last file")
    print("           'list' = show added files     'q' = cancel")

    files: list[Path] = []

    while True:
        prompt = f"\nFile #{len(files) + 1}: "
        user_input = input(prompt).strip()
        command = user_input.lower()

        if command in {"q", "quit", "cancel"}:
            print("Combine cancelled.")
            return

        if command == "":
            # An empty line doesn't end the loop, so an accidental Enter can't cut it short
            print("Nothing entered. Type a file name, or 'done' when you have added all files.")
            continue

        if command == "list":
            if not files:
                print("No files added yet.")
            for i, f in enumerate(files, start=1):
                print(f"  {i}. {f.name}")
            continue

        if command == "undo":
            if files:
                print(f"Removed: {files.pop().name}")
            else:
                print("Nothing to undo.")
            continue

        if command == "done":
            if len(files) < 2:
                print(f"Error: you need at least 2 PDF files to combine (added so far: {len(files)}).")
                continue
            break

        # Otherwise treat the input as a file name
        try:
            pdf_path = validate_file(user_input)
            reader = open_pdf(pdf_path)  # validates the PDF right away
            files.append(pdf_path)
            print(f"Added: {pdf_path.name} ({len(reader.pages)} page(s))")
        except ValueError as err:
            print(f"Error: {err}")
        except PermissionError:
            print("Error: permission denied. Check the file permissions.")
        except OSError as err:
            print(f"Error: could not read the file ({err}).")

    # Choose output name and merge
    out_path = ask_output_path(files[0].parent, files)
    if out_path is None:
        print("Combine cancelled.")
        return

    try:
        writer = PdfWriter()
        total_pages = 0
        for pdf_path in files:
            reader = open_pdf(pdf_path)
            for page in reader.pages:
                writer.add_page(page)
            total_pages += len(reader.pages)

        with open(out_path, "wb") as f:
            writer.write(f)
        print(f"\nCombined {len(files)} files ({total_pages} pages) into: {out_path}")
    except ValueError as err:
        print(f"Error: {err}")
    except PermissionError:
        print("Error: permission denied. Check the file/folder permissions.")
    except OSError as err:
        print(f"Error: could not read or write files ({err}).")
    except Exception as err:  # last-resort safety net
        print(f"Unexpected error: {err}")


# --------------------------------------------------------------------------
# Rotate mode
# --------------------------------------------------------------------------

def ask_rotation() -> tuple[str, int] | None:
    """Ask for the rotation direction. Returns (label, angle) or None if cancelled."""
    while True:
        answer = input("\nRotate to the left or right? (l/r, or 'q' to go back): ").strip().lower()
        if answer in {"q", "quit", "exit"}:
            return None
        if answer in {"l", "left"}:
            return "left", 270  # 90 degrees counter-clockwise
        if answer in {"r", "right"}:
            return "right", 90  # 90 degrees clockwise
        print("Error: please enter 'l' for left or 'r' for right.")


def rotate_pdf(pdf_path: Path, label: str, angle: int) -> Path | None:
    """Rotate every page and save as a new file. Returns the output path, or None if skipped."""
    reader = open_pdf(pdf_path)

    # Save next to the original; never overwrite the original file
    out_path = pdf_path.with_name(f"{pdf_path.stem}_rotated_{label}.pdf")
    if out_path.exists():
        answer = input(f"'{out_path.name}' already exists. Overwrite? (y/n): ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Rotation cancelled.")
            return None

    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(angle)
        writer.add_page(page)

    with open(out_path, "wb") as f:
        writer.write(f)

    print(f"Rotated {len(reader.pages)} page(s) to the {label}. Saved as: {out_path}")
    return out_path


def rotate_mode() -> None:
    print("\n--- Rotate mode ---")
    while True:
        user_input = input("\nWhich PDF file would you like to rotate? (or 'q' to go back): ").strip()

        if user_input.lower() in {"q", "quit", "exit"}:
            return
        if not user_input:
            print("Error: please enter a file name.")
            continue

        try:
            pdf_path = validate_file(user_input)
            open_pdf(pdf_path)  # check the PDF is usable before asking for the direction

            rotation = ask_rotation()
            if rotation is None:
                return
            label, angle = rotation

            rotate_pdf(pdf_path, label, angle)
            return
        except ValueError as err:
            print(f"Error: {err}")
        except PermissionError:
            print("Error: permission denied. Check the file/folder permissions.")
        except OSError as err:
            print(f"Error: could not read or write files ({err}).")
        except Exception as err:  # last-resort safety net
            print(f"Unexpected error: {err}")


# --------------------------------------------------------------------------
# Main menu
# --------------------------------------------------------------------------

def main() -> None:
    print("=== PDF Tool ===")
    while True:
        print("\nWhat would you like to do?")
        print("  1 - Split a PDF into single pages")
        print("  2 - Combine multiple PDFs into one")
        print("  3 - Rotate a PDF to the left or right")
        choice = input("Enter 1, 2 or 3 (or 'q' to quit): ").strip().lower()

        if choice == "1":
            split_mode()
        elif choice == "2":
            combine_mode()
        elif choice == "3":
            rotate_mode()
        elif choice in {"q", "quit", "exit"}:
            print("Goodbye!")
            break
        else:
            print("Error: please enter 1, 2, 3 or q.")


if __name__ == "__main__":
    main()
