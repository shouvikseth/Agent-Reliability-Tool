import pytest
from lab.report import summarize


def fixture():
    rows = [{'task': 'a', 'repetition': index, 'architecture': 'fixed', 'id': str(index)} for index in (1, 2)]
    results = {row['id']: {'status': 'submitted', 'verified_completion': row['id']=='1', 'seconds': 2,
        'tokens': 5, 'dollars': 0, 'verification': {'regression': {'passed': row['id']=='1'}}} for row in rows}
    return rows, results


def test_report_counts_failures_and_consistency():
    rows, results = fixture()
    summary = summarize(rows, rows, results)
    assert summary['architectures']['fixed']['verified'] == 1
    assert summary['architectures']['fixed']['scheduled'] == 2
    assert summary['architectures']['fixed']['regression_failures'] == 1
    assert summary['task_consistency']['a']['fixed'] == {'successes': 1, 'repetitions': 2}


@pytest.mark.parametrize('indices', [[0], [0, 0]])
def test_incomplete_or_duplicated_outcomes_refused(indices):
    rows, results = fixture()
    with pytest.raises(ValueError):
        summarize(rows, [rows[index] for index in indices], results)
