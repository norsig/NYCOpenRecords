import unittest
from app import create_app, db, es
from app.models import Roles, Agencies, Reasons
from app.search.utils import (
    create_index,
    delete_index,
    delete_docs,
    index_exists,
)


class BaseTestCase(unittest.TestCase):
    app = create_app('testing', jobs_enabled=False)

    @classmethod
    def setUpClass(cls, create_db=True, create_es_index=True):
        with cls.app.app_context():
            if create_db:
                db.create_all()
            if create_es_index:
                if index_exists():
                    delete_index()
                create_index()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            delete_index()

    def setUp(self, populate=True):
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        if populate:
            self.populate_database()

    def tearDown(self):
        delete_docs()
        self.clear_database()
        self.app_context.pop()

    @staticmethod
    def clear_database():
        meta = db.metadata
        for table in reversed(meta.sorted_tables):
            db.session.execute(table.delete())
        for sequence in ("reasons_id_seq", "roles_id_seq"):
            db.session.execute("ALTER SEQUENCE {} RESTART WITH 1;".format(sequence))
        db.session.commit()

    @staticmethod
    def populate_database():
        list(map(lambda x: x.populate(), (
            Roles,
            Agencies,
            Reasons,
        )))
