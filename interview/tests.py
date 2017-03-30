from django.test import TestCase

from interview.factory import ProcessFactory, InterviewFactory


class ProcessTestCase(TestCase):
    def test_state(self):
        p = ProcessFactory()
        i1 = InterviewFactory(process=p, rank=1, next_state='GO')
        i3 = InterviewFactory(process=p, rank=3, next_state='PL')
        i2 = InterviewFactory(process=p, rank=2, next_state='NO')
        self.assertEqual(p.state, i3.next_state)
