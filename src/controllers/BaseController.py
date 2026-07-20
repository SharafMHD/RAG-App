from helpers.config import get_settings
import os


class BaseController:
    def __init__(self):
        self.app_settings = get_settings()
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.file_dir = os.path.join(self.base_dir, self.app_settings.UPLOAD_DIR)
        self.vector_dbs_dir = os.path.join(self.base_dir, self.app_settings.VECTOR_DBS_DIR)

    def get_vector_db_path(self, db_name: str):
        database_path = os.path.join(self.vector_dbs_dir, db_name)
        os.makedirs(database_path, exist_ok=True)
        return database_path

