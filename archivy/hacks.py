from pathlib import Path
from flask import current_app


class Hacks(object):

    _data_dir = None

    @classmethod
    def get_data_dir(cls):
        # FIXME: ugly hack to make sure the app path is evaluated at the right time
        if cls._data_dir is None:
            cls._data_dir = Path(current_app.config["USER_DIR"]) / "data"
        return cls._data_dir
