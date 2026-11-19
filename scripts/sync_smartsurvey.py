import logging

from smartsurvey_download import download_surveys
from import_smartsurvey import run as import_surveys
from populate_participant_test_scores import main as populate_test_scores
from import_hair_status import run as import_hair_status


'''
Download SmartSurvey exports, import records, populate scores, then import hair status.

Input: None; uses the existing download, import, score, and hair-status configuration.
Output: None; prints progress and saves validated changes to PostgreSQL.
Errors stop the workflow and are raised to the caller.
'''

def sync_surveys():
    try:
        download_surveys()
        import_surveys(auto_save=True)
        populate_test_scores()
        import_hair_status(apply=True)
    except Exception:
        logging.exception("SmartSurvey synchronization failed")
        raise

    print("SmartSurvey synchronization completed.")


if __name__ == "__main__":
    sync_surveys()
