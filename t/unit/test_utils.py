from unittest import TestCase

import dill
from celery.canvas import Signature

from django_celery_beat.utils import sign_task_signature, verify_task_signature


class UtilsTests(TestCase):
    test_private_key_path = './test_id_rsa'
    test_public_key_path = './test_id_rsa.pub'

    def test_sign_verify_task_signature(self):
        empty_task_signature = Signature()

        serialized_empty_task = dill.dumps(empty_task_signature)
        s = sign_task_signature(serialized_empty_task)

        is_valid = verify_task_signature(serialized_empty_task, s)

        self.assertTrue(is_valid)
