import os
from unittest import TestCase

import dill
from celery.canvas import Signature

from django_celery_beat.utils import sign_task_signature, _load_keys, verify_task_signature


class UtilsTests(TestCase):
    test_private_key_path = './test_id_rsa'
    test_public_key_path = './test_id_rsa.pub'

    @classmethod
    def setUpClass(cls) -> None:
        super(UtilsTests, cls).setUpClass()

        os.environ.update({
            'DJANGO_CELERY_BEAT_PRIVATE_KEY_PATH': cls.test_private_key_path,
            'DJANGO_CELERY_BEAT_PUBLIC_KEY_PATH': cls.test_public_key_path,
        })

        _load_keys()

    def test_sign_verify_task_signature(self):
        empty_task_signature = Signature()

        serialized_empty_task = dill.dumps(empty_task_signature)
        s = sign_task_signature(serialized_empty_task)

        is_valid = verify_task_signature(serialized_empty_task, s)

        self.assertTrue(is_valid)

    @classmethod
    def tearDownClass(cls) -> None:
        super(UtilsTests, cls).tearDownClass()

        if os.path.exists(cls.test_private_key_path):
            os.remove(cls.test_private_key_path)

        if os.path.exists(cls.test_public_key_path):
            os.remove(cls.test_public_key_path)
