/* Shared district map for the public pages.
   One inline SVG holds a geographic view and an equal-area tile view of the same
   districts. Pages supply colors, names and callbacks; this module owns drawing,
   the Map/Tiles transition, zoom, hover, selection and a single keyboard tab stop
   (arrow keys move between districts, Enter or Space selects). */
window.SiteMap = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const motionOK = () => !(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  let instances = 0;

  function node(name, attrs, parent) {
    const item = document.createElementNS(NS, name);
    for (const [key, value] of Object.entries(attrs || {})) if (value != null) item.setAttribute(key, value);
    if (parent) parent.appendChild(item);
    return item;
  }

  function luminance(hex) {
    const match = /^#?([0-9a-f]{6})$/i.exec(String(hex || "").trim());
    if (!match) return 1;
    const channel = i => {
      const v = parseInt(match[1].slice(i, i + 2), 16) / 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4);
  }

  function create(container, spec) {
    const uid = `sm${++instances}`;
    const geometry = spec.geometry;
    const ids = Object.keys(geometry.districts).sort((a, b) => (+a - +b) || String(a).localeCompare(String(b)));
    const full = (geometry.viewBox || [0, 0, 640, 700]).map(Number);
    const context = spec.context || {};
    let view = "map", selected = null, focusId = ids[0], box = full.slice(), frame = null, area = null;

    container.innerHTML = "";
    container.classList.add("sm");
    container.dataset.view = view;
    const svg = node("svg", {
      class: "sm-svg", viewBox: full.join(" "), role: "group",
      "aria-label": spec.label || "District map",
      "aria-roledescription": "map",
    }, container);
    const help = document.createElement("p");
    help.className = "sr-only";
    help.id = `${uid}-help`;
    help.textContent = "Use the arrow keys to move between districts and Enter to open one.";
    container.appendChild(help);
    svg.setAttribute("aria-describedby", help.id);
    const defs = node("defs", {}, svg);
    const hatch = node("pattern", {
      id: `${uid}-hatch`, patternUnits: "userSpaceOnUse", width: 5, height: 5, patternTransform: "rotate(45)",
    }, defs);
    node("rect", { width: 1.6, height: 5, fill: "#ffffff", opacity: 0.85 }, hatch);

    const base = node("g", { class: "sm-base", "aria-hidden": "true" }, svg);
    if (geometry.outline) node("path", { class: "sm-outline", d: geometry.outline }, base);
    const geo = node("g", { class: "sm-geo" }, svg);
    const hatches = node("g", { class: "sm-hatches", "aria-hidden": "true" }, svg);
    const ctx = node("g", { class: "sm-context", "aria-hidden": "true" }, svg);
    if (context.counties) node("path", { class: "sm-counties", d: context.counties }, ctx);
    const outlineTop = node("g", { class: "sm-selection", "aria-hidden": "true" }, svg);
    const tiles = node("g", { class: "sm-tiles" }, svg);
    const cities = node("g", { class: "sm-cities", "aria-hidden": "true" }, svg);
    for (const city of context.cities || []) {
      const group = node("g", { class: "sm-city" }, cities);
      node("circle", { cx: city.x, cy: city.y, r: 2.2 }, group);
      const label = node("text", { x: city.x + 5, y: city.y + 3.5 }, group);
      label.textContent = city.name;
    }

    const paths = new Map(), tileNodes = new Map(), hatchNodes = new Map();
    const tileSize = +geometry.tileSize || 20;
    for (const id of ids) {
      const district = geometry.districts[id];
      const path = node("path", {
        class: "sm-d", d: district.path, id: `${uid}-d-${id}`, "data-id": id,
        role: "button", tabindex: "-1", "vector-effect": "non-scaling-stroke",
      }, geo);
      paths.set(id, path);
      // A separate path, not <use>: the district's own fill would override a <use> pattern fill.
      // Its outline is copied only when the district is first hatched.
      const overlay = node("path", { fill: `url(#${uid}-hatch)`, class: "sm-hatch" }, hatches);
      overlay.style.display = "none";
      hatchNodes.set(id, overlay);
      const tile = geometry.tiles && geometry.tiles[id];
      if (tile) {
        const group = node("g", { class: "sm-t", "data-id": id, role: "button", tabindex: "-1" }, tiles);
        const s = tileSize * 0.9;
        node("rect", { class: "sm-t-fill", x: -s / 2, y: -s / 2, width: s, height: s, rx: 1.5 }, group);
        node("rect", { class: "sm-t-hatch", x: -s / 2, y: -s / 2, width: s, height: s, rx: 1.5, fill: `url(#${uid}-hatch)` }, group);
        const label = node("text", { class: "sm-t-label", y: s * 0.13, "font-size": Math.max(7, s * 0.36).toFixed(1) }, group);
        label.textContent = spec.tileLabel ? spec.tileLabel(id) : id;
        group.dataset.tx = tile[0]; group.dataset.ty = tile[1];
        group.dataset.lx = district.label[0]; group.dataset.ly = district.label[1];
        tileNodes.set(id, group);
      }
    }

    const tip = document.createElement("div");
    tip.className = "sm-tip";
    tip.setAttribute("role", "tooltip");
    tip.hidden = true;
    container.appendChild(tip);

    function placeTiles(animate) {
      for (const group of tileNodes.values()) {
        const inTiles = view === "tiles";
        const x = inTiles ? group.dataset.tx : group.dataset.lx;
        const y = inTiles ? group.dataset.ty : group.dataset.ly;
        group.style.transition = animate && motionOK() ? "" : "none";
        group.style.transform = `translate(${x}px, ${y}px) scale(${inTiles ? 1 : 0.18})`;
      }
    }

    function interactive(id) {
      return view === "tiles" && tileNodes.has(id) ? tileNodes.get(id) : paths.get(id);
    }

    function setRoving(id) {
      focusId = id;
      for (const [key, path] of paths) path.setAttribute("tabindex", view === "map" && key === id ? "0" : "-1");
      for (const [key, group] of tileNodes) group.setAttribute("tabindex", view === "tiles" && key === id ? "0" : "-1");
    }

    function textColor(fill) {
      const l = luminance(fill);
      return 1.05 / (l + 0.05) >= (l + 0.05) / 0.0658 ? "#ffffff" : "#1d2228";
    }

    function refresh() {
      for (const id of ids) {
        const fill = spec.fill(id);
        const path = paths.get(id);
        path.setAttribute("fill", fill);
        path.classList.toggle("is-dashed", Boolean(spec.dashed && spec.dashed(id)));
        const muted = Boolean(spec.muted && spec.muted(id));
        path.classList.toggle("is-dim", muted);
        const label = spec.name ? spec.name(id) : `District ${id}`;
        path.setAttribute("aria-label", label);
        const hatched = Boolean(spec.hatch && spec.hatch(id));
        const overlay = hatchNodes.get(id);
        if (hatched && !overlay.hasAttribute("d")) overlay.setAttribute("d", path.getAttribute("d"));
        overlay.classList.toggle("is-dim", muted);
        overlay.style.display = hatched ? "" : "none";
        const group = tileNodes.get(id);
        if (group) {
          group.querySelector(".sm-t-fill").setAttribute("fill", fill);
          group.querySelector(".sm-t-hatch").style.display = hatched ? "" : "none";
          group.querySelector(".sm-t-label").setAttribute("fill", textColor(fill));
          group.setAttribute("aria-label", label);
          group.classList.toggle("is-dim", muted);
        }
      }
      drawSelection();
    }

    function drawSelection() {
      outlineTop.innerHTML = "";
      const hasSelection = Boolean(selected && paths.has(selected));
      svg.classList.toggle("has-selection", hasSelection);
      for (const id of ids) {
        const on = id === selected;
        paths.get(id).setAttribute("aria-pressed", on ? "true" : "false");
        paths.get(id).classList.toggle("is-selected", on);
        hatchNodes.get(id).classList.toggle("is-selected", on);
        const group = tileNodes.get(id);
        if (group) {
          group.setAttribute("aria-pressed", on ? "true" : "false");
          group.classList.toggle("is-selected", on);
        }
      }
      if (hasSelection) {
        const d = paths.get(selected).getAttribute("d");
        node("path", { class: "sm-selected-halo", d, "vector-effect": "non-scaling-stroke" }, outlineTop);
        node("path", { class: "sm-selected-outline", d, "vector-effect": "non-scaling-stroke" }, outlineTop);
      }
    }

    function setBox(next) {
      box = next;
      svg.setAttribute("viewBox", box.map(v => v.toFixed(2)).join(" "));
      const k = box[2] / full[2];
      svg.style.setProperty("--sm-k", k.toFixed(4));
      // Hatch stripes keep the same on-screen spacing at every zoom.
      for (const attr of ["width", "height"]) hatch.setAttribute(attr, (5 * k).toFixed(3));
      hatch.firstChild.setAttribute("width", (1.6 * k).toFixed(3));
      hatch.firstChild.setAttribute("height", (5 * k).toFixed(3));
      for (const label of cities.querySelectorAll("text")) {
        label.style.fontSize = `${(10.5 * k).toFixed(2)}px`;
        label.style.strokeWidth = `${(3 * k).toFixed(2)}px`;
      }
      for (const dot of cities.querySelectorAll("circle")) dot.setAttribute("r", (2.2 * k).toFixed(2));
    }

    function animateTo(target) {
      cancelAnimationFrame(frame);
      const start = box.slice(), began = performance.now(), duration = motionOK() ? 520 : 0;
      const ease = t => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
      const step = now => {
        const t = duration ? Math.min(1, (now - began) / duration) : 1;
        setBox(start.map((v, i) => v + (target[i] - v) * ease(t)));
        if (t < 1) frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    }

    function fitBox(raw, minimum) {
      let [x, y, w, h] = raw;
      const aspect = full[2] / full[3];
      w = Math.max(w * 1.6, minimum); h = Math.max(h * 1.6, minimum / aspect);
      if (w / h > aspect) h = w / aspect; else w = h * aspect;
      const cx = raw[0] + raw[2] / 2, cy = raw[1] + raw[3] / 2;
      w = Math.min(w, full[2]); h = Math.min(h, full[3]);
      x = Math.min(Math.max(full[0], cx - w / 2), full[0] + full[2] - w);
      y = Math.min(Math.max(full[1], cy - h / 2), full[1] + full[3] - h);
      return [x, y, w, h];
    }

    function zoomTo(raw) { if (view === "map") animateTo(fitBox(raw, 70)); }
    function reset() { animateTo(full.slice()); }

    function select(id, options = {}) {
      selected = id && paths.has(String(id)) ? String(id) : null;
      drawSelection();
      if (selected) {
        setRoving(selected);
        if (options.zoom !== false && view === "map") {
          const b = paths.get(selected).getBBox();
          zoomTo([b.x, b.y, b.width, b.height]);
        }
      } else if (options.zoom !== false && !area) {
        reset();
      }
    }

    function highlight(id) {
      for (const [key, path] of paths) path.classList.toggle("is-hover", key === String(id));
      for (const [key, group] of tileNodes) group.classList.toggle("is-hover", key === String(id));
    }

    function focusArea(name) {
      const metro = (context.metros || []).find(m => m.name === name);
      area = metro ? name : null;
      const members = new Set(((geometry.metroMembers || []).find(m => m.name === name) || {}).members || []);
      for (const [key, group] of tileNodes) group.classList.toggle("is-muted", Boolean(area) && view === "tiles" && !members.has(key));
      if (!metro) { reset(); return; }
      if (view === "map") animateTo(fitBox(metro.box, 70));
    }

    function setView(next) {
      view = next === "tiles" ? "tiles" : "map";
      container.dataset.view = view;
      geo.setAttribute("aria-hidden", String(view === "tiles"));
      tiles.setAttribute("aria-hidden", String(view === "map"));
      if (view === "tiles") { cancelAnimationFrame(frame); setBox(full.slice()); }
      placeTiles(true);
      setRoving(selected || focusId);
      for (const group of tileNodes.values()) group.classList.remove("is-muted");
      if (area) focusArea(area);
      else if (view === "map" && selected) select(selected);
    }

    function showTip(event, id) {
      if (!spec.describe) return;
      tip.innerHTML = spec.describe(id);
      tip.hidden = false;
      const bounds = container.getBoundingClientRect();
      const x = event.clientX - bounds.left, y = event.clientY - bounds.top;
      const width = tip.offsetWidth, height = tip.offsetHeight;
      tip.style.left = `${Math.min(Math.max(8, x + 14), bounds.width - width - 8)}px`;
      tip.style.top = `${Math.max(8, y - height - 12)}px`;
    }

    function hideTip() { tip.hidden = true; }

    function targetId(event) {
      const target = event.target.closest("[data-id]");
      return target && svg.contains(target) ? target.dataset.id : null;
    }

    svg.addEventListener("pointermove", event => {
      const id = targetId(event);
      if (!id) { hideTip(); highlight(null); if (spec.onHover) spec.onHover(null); return; }
      highlight(id); showTip(event, id);
      if (spec.onHover) spec.onHover(id);
    });
    svg.addEventListener("pointerleave", () => { hideTip(); highlight(null); if (spec.onHover) spec.onHover(null); });
    svg.addEventListener("click", event => {
      hideTip();
      const id = targetId(event);
      if (id && spec.onSelect) spec.onSelect(id);
    });
    svg.addEventListener("keydown", event => {
      const id = targetId(event) || focusId;
      const index = ids.indexOf(id);
      const moves = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
      let next = null;
      if (event.key in moves) next = ids[(index + moves[event.key] + ids.length) % ids.length];
      else if (event.key === "Home") next = ids[0];
      else if (event.key === "End") next = ids[ids.length - 1];
      else if ((event.key === "Enter" || event.key === " ") && id) {
        event.preventDefault();
        if (spec.onSelect) spec.onSelect(id);
        return;
      }
      if (next) {
        event.preventDefault();
        setRoving(next);
        interactive(next).focus();
        highlight(next);
        if (spec.onHover) spec.onHover(next);
      }
    });
    svg.addEventListener("focusout", event => {
      if (!svg.contains(event.relatedTarget)) { highlight(null); if (spec.onHover) spec.onHover(null); }
    });

    setBox(full.slice());
    placeTiles(false);
    setRoving(focusId);
    refresh();
    return { element: svg, refresh, select, highlight, zoomTo, reset, setView, focusArea,
      get view() { return view; }, ids };
  }

  return { create };
})();
