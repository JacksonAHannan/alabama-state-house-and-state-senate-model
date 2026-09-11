// Open project_docs/PROJECT_COMPLETION_CHECKLIST.html, then evaluate this script.
// Uses the existing browser runner; no test dependency or public-site integration.
(() => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const before = structuredClone(state);
  const stored = localStorage.getItem(storageKey);
  const checks = [];
  try {
    assert(tasks().length === 82 && state.phases.length === 7, 'Baseline scope');
    assert(new Set(tasks().map(task => task.id)).size === tasks().length, 'Unique task IDs');
    assert(document.querySelectorAll('.task input[type=checkbox]').length === tasks().length, 'Every task rendered');
    assert(valid(state), 'Valid initial snapshot');
    checks.push('scope, stable IDs, snapshot and checkbox coverage');
    const task = tasks().find(task => !task.done), original = count(), events = state.history.length;
    document.getElementById(task.id).click();
    assert(count() === original + 1 && state.history.length === events + 1, 'Checking adds snapshot');
    assert(document.getElementById('counter').textContent.startsWith(String(original + 1) + ' /'), 'Counter updates');
    assert(JSON.parse(localStorage.getItem(storageKey)).phases.flatMap(phase => phase.tasks).find(item => item.id === task.id).done, 'Draft persisted');
    document.getElementById(task.id).click();
    assert(count() === original && state.history.at(-1).done === original, 'Unchecking records decrease');
    assert(document.querySelectorAll('#chart circle').length === state.history.length, 'Chart contains all snapshots');
    assert(document.querySelectorAll('#history tr').length === state.history.length, 'Accessible history parity');
    checks.push('check, uncheck, persistence, counter and chart history');
    const query = document.getElementById('search'); query.value = task.id; query.dispatchEvent(new Event('input'));
    assert(document.querySelectorAll('.task:not([hidden])').length === 1, 'Search isolates task');
    query.value = 'no-such-task-xyz'; query.dispatchEvent(new Event('input'));
    assert(!document.getElementById('no-results').hidden, 'Empty filter message');
    query.value = ''; document.getElementById('product').value = 'Southern legislative WAR'; filter();
    assert(document.querySelectorAll('.task:not([hidden])').length === 13, 'Workstream filter');
    document.getElementById('product').value = ''; document.getElementById('status').value = 'done'; filter();
    assert(document.querySelectorAll('.task:not([hidden])').length === original, 'Status filter');
    checks.push('search, empty state, workstream and status filters');
    const note = document.querySelector('#task-' + task.id + ' textarea');
    note.value = '</script><script>window.CHECKLIST_INJECTION=true</script> & evidence';
    note.dispatchEvent(new Event('input'));
    const exported = exportedHTML(), parsed = new DOMParser().parseFromString(exported, 'text/html');
    const saved = JSON.parse(parsed.getElementById('checklist-data').textContent);
    assert(saved.revision !== seed.revision, 'Export has fresh revision');
    assert(saved.history.length === state.history.length, 'Export retains history');
    assert(saved.phases.flatMap(phase => phase.tasks).find(item => item.id === task.id).evidence === note.value, 'Evidence round-trip');
    assert(parsed.querySelectorAll('script').length === 2 && !window.CHECKLIST_INJECTION, 'Evidence cannot inject script');
    assert(parsed.querySelectorAll('#product option').length === 1, 'Export does not duplicate dynamic options');
    const bad = structuredClone(state); bad.history.at(-1).done = -1;
    assert(!valid(bad), 'Reject malformed draft');
    checks.push('portable HTML export, evidence escaping, fresh revision and malformed-draft guard');
    document.getElementById('status').value = ''; filter();
    assert(document.documentElement.scrollWidth <= innerWidth, 'No horizontal page overflow');
    checks.push('viewport overflow');
    return {passed: checks, width: innerWidth, tasks: tasks().length};
  } finally {
    state = before;
    if (stored === null) localStorage.removeItem(storageKey); else localStorage.setItem(storageKey, stored);
    for (const id of ['search', 'product', 'status']) document.getElementById(id).value = '';
    render();
    document.getElementById('save-status').textContent = 'Browser checks restored the original progress; no test edits retained.';
  }
})()
