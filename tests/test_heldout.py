from collections import Counter

from lab.heldout import HELDOUT_TASKS, schedule, task_fingerprints
from lab.tasks import TASKS, seed


def test_heldout_catalog_is_disjoint_and_seedable(tmp_path):
    assert len(HELDOUT_TASKS)==12
    assert {t.id for t in HELDOUT_TASKS}.isdisjoint(t.id for t in TASKS)
    assert Counter(t.category for t in HELDOUT_TASKS)==dict.fromkeys(
        ('pagination','validation','transitions','duplicates'),3)
    development_seeds={task_fingerprints(t)['seed_sha256'] for t in TASKS}
    for task in HELDOUT_TASKS:
        assert task.split=='heldout'
        seed(task,tmp_path/task.id)
        assert task_fingerprints(task)['seed_sha256'] not in development_seeds


def test_heldout_design_accounts_for_all_slots_and_balanced_faults():
    rows=schedule(42)
    assert rows==schedule(42)
    assert len(rows)==len({r['attempt_id'] for r in rows})==216
    assert Counter(r['architecture'] for r in rows)==dict.fromkeys(('fixed','single','team'),72)
    assert Counter(r['condition'] for r in rows)=={'clean':108,'timeout':54,'malformed':54}
    for task in HELDOUT_TASKS:
        group=[r for r in rows if r['task']==task.id]
        assert len(group)==18
        for repetition in range(1,4):
            for condition in {r['condition'] for r in group}:
                assert sorted(r['architecture'] for r in group if r['repetition']==repetition and r['condition']==condition)==['fixed','single','team']
    assert {r['attempt_id'] for r in rows}.isdisjoint(r['attempt_id'] for r in schedule(43))
