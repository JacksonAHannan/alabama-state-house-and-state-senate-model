// Run in the Southern page with agent-browser eval -b (base64 file contents).
(() => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const change = (selector, value) => {
    const element = document.querySelector(selector);
    element.value = String(value);
    element.dispatchEvent(new Event('change', {bubbles: true}));
  };
  let checked = 0, scored = 0, empty = 0;
  assert(Object.keys(DATA.slices).length === 116, 'Expected 116 scheduled slices');
  assert(color(null) !== color(0), 'Missing and zero must have different colors');
  assert(color(30) === color(300) && color(-30) === color(-300), 'Symmetric 30-point color cap');
  for (const slice of Object.values(DATA.slices)) {
    change('#state', slice.state);
    change('#cycle', slice.cycle);
    change('#chamber', slice.chamber);
    assert(active === slice, `Filter selection lost ${slice.state}/${slice.cycle}/${slice.chamber}`);
    assert(selected === null && !document.querySelector('.racebox'), 'Previous race leaked into new slice');
    assert(document.querySelectorAll('#map .district').length === slice.districts, 'District outline count');
    const race = Object.values(slice.races)[0];
    if (race) {
      const path = [...document.querySelectorAll('#map .district')].find(p => p.dataset.district === race.district);
      path.focus();
      path.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
      assert(selected === race.district, 'Keyboard district selection');
      assert(document.activeElement === path, 'District selection must preserve keyboard focus');
      const box = document.querySelector('#detail .racebox');
      assert(box && box.textContent.includes(race.demCandidate) && box.textContent.includes(race.repCandidate), 'Both candidate names in wikibox');
      assert(box.textContent.includes(count(race.demVotes)) && box.textContent.includes(count(race.repVotes)), 'Observed vote totals in wikibox');
      assert(box.querySelectorAll('tbody tr').length === 2, 'Exactly two major-party outcome rows');
      assert(getComputedStyle(box.querySelector('td.num')).whiteSpace === 'nowrap', 'Vote totals must not split across lines');
      const boxRect = box.getBoundingClientRect(), mapRect = document.querySelector('.map-panel').getBoundingClientRect();
      assert(innerWidth <= 780 ? boxRect.top >= mapRect.bottom : boxRect.left >= mapRect.right, 'Wikibox placement');
      document.querySelector('[data-metric="rawGap"]').click();
      assert(selected === race.district && document.querySelector('.racebox'), 'Metric switch must retain race');
      document.querySelector('[data-metric="war"]').click();
      document.querySelector('.close-detail').click();
      assert(selected === null && document.activeElement.id === 'district', 'Close restores district selector focus');
      document.querySelector('.row-link').click();
      assert(selected !== null && document.querySelector('.racebox'), 'Race-table selection');
      scored++;
    } else {
      empty++;
      assert(document.querySelector('#rows').textContent.includes('No strict WAR-eligible'), 'Empty slice explanation');
    }
    const missing = slice.features.find(f => !slice.races[f.district]);
    if (missing) {
      change('#district', missing.district);
      assert(document.querySelector('#detail').textContent.includes('Missing WAR is not zero'), 'Unscored district explanation');
      assert(!document.querySelector('.racebox'), 'No invented race results');
    }
    assert(document.documentElement.scrollWidth <= innerWidth, 'No horizontal page overflow');
    checked++;
  }
  change('#state', 'TX'); change('#cycle', 2024); change('#chamber', 'lower'); change('#district', 70);
  return {checkedSlices: checked, scoredSlices: scored, emptySlices: empty, viewport: innerWidth, status: 'passed'};
})();
