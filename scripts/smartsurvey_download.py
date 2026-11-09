
from pathlib import Path
from datetime import datetime
import logging
import re

from dotenv import dotenv_values
import win32com.client


# -------------------------------------------
# CONFIGURATION
# -------------------------------------------

DOWNLOAD_FOLDER = Path(r"D:\HairProject\SmartSurvey")

SURVEY_MAPPING = {
    "1781743": "Questionnaire1",
    "1781777": "Questionnaire2",
}

ALLOWED_EXTENSIONS = {".csv", ".xlsx"}

EXPECTED_MAILBOX = dotenv_values(
    Path(__file__).resolve().parents[1] / ".env"
).get("SMARTSURVEY_MAILBOX", "")

# -------------------------------------------
# CONNECT TO OUTLOOK
# -------------------------------------------

def connect_outlook():
    outlook = win32com.client.Dispatch("Outlook.Application")
    namespace = outlook.GetNamespace("MAPI")

    inbox = namespace.GetDefaultFolder(6)
    mailbox = inbox.Store.DisplayName

    print("Connected to Outlook:", mailbox)

    if mailbox.lower() != EXPECTED_MAILBOX.lower():
        raise RuntimeError(
            "Unexpected Outlook mailbox: " + mailbox
        )

    return inbox


# -------------------------------------------
# IDENTIFY QUESTIONNAIRE
# -------------------------------------------

def identify_questionnaire(filename):
    match = re.match(
        r"^RawData-(\d+)-",
        filename,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    survey_id = match.group(1)

    return SURVEY_MAPPING.get(survey_id)


# -------------------------------------------
# DOWNLOAD ATTACHMENTS
# -------------------------------------------

def download_surveys():

    DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=str(DOWNLOAD_FOLDER / "download.log"),
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    inbox = connect_outlook()

    messages = inbox.Items
    messages.Sort("[ReceivedTime]", True)

    downloaded = 0
    skipped = 0
    failed = 0
    
    processed_questionnaires = set()

    print("Checking SmartSurvey emails...")

    for message in messages:

        try:
            if message.Class != 43: #43 means that it is an email
                continue

            subject = str(message.Subject or "")

            if "SmartSurvey Exported Data" not in subject:
                continue

            sender = str(
                message.SenderEmailAddress or ""
            ).lower()

            if sender != "member@smartsurveyuser.com":
                print("Skipped unexpected sender:", sender)
                continue
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
            for attachment in message.Attachments:

                filename = attachment.FileName

                extension = Path(filename).suffix.lower()

                if extension not in ALLOWED_EXTENSIONS:
                    continue

                questionnaire = identify_questionnaire(filename)

                if questionnaire is None:
                    print("Unknown questionnaire:", filename)
                    continue
                
                # Only process the newest export for each questionnaire
                if questionnaire in processed_questionnaires:
                    continue

                processed_questionnaires.add(questionnaire)

                new_filename = questionnaire + "_" + filename

                destination = DOWNLOAD_FOLDER / new_filename

                if destination.exists():
                    print("Already downloaded:", new_filename)
                    skipped += 1
                    continue

                attachment.SaveAsFile(str(destination))

                if not destination.is_file() or destination.stat().st_size == 0:
                    raise RuntimeError(
                        "Attachment was not saved correctly"
                    )

                print("Downloaded:", new_filename)

                logging.info(
                    "Downloaded %s from email %s",
                    new_filename,
                    subject
                )

                downloaded += 1

        except Exception as error:
            failed += 1
            print("Error processing email:", error)
            logging.exception("Email processing failed")

    print()
    print("Download completed")
    print("New files:", downloaded)
    print("Already downloaded:", skipped)
    print("Folder:", DOWNLOAD_FOLDER)
    print("Failed emails:", failed)

    if failed:
        raise RuntimeError(
            f"SmartSurvey download failed for {failed} email(s). "
            "Review download.log before importing."
        )


# -------------------------------------------
# MAIN
# -------------------------------------------

if __name__ == "__main__":

    print("SmartSurvey automatic downloader")
    print("Started:", datetime.now())

    download_surveys()

    print("Finished:", datetime.now())
