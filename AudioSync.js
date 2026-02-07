/*
 * AudioSync.js — Max for Live Transient Alignment Tool
 * =====================================================
 *
 * SELF-BOOTSTRAPPING: On loadbang this script creates all UI controls
 * (Analyze, Reset, Scope menu, Track-IDs field, Offset cap, Status)
 * directly in the Max patcher via this.patcher.newdefault() and wires
 * them to itself.  No hand-built .amxd required.
 *
 * SETUP (one-time, ~1 minute):
 *   1. In Live 12, drag "Max Audio Effect" from the browser onto a track
 *   2. Click the device's Edit button to open the Max editor
 *   3. Press N, type:  js AudioSync.js   — press Enter
 *   4. The script auto-creates all UI on loadbang
 *   5. Save the device  (Cmd+S / Ctrl+S)
 *
 * Aligns audio clips across multiple tracks by matching first transients.
 * Supports arrangement & session clips, group & manual track selection,
 * and any number of clips per track.
 *
 * MESSAGES (inlet 0):
 *   analyze            full pipeline: discover, detect, align
 *   reset              undo last alignment (restore original start_markers)
 *   scope <int>        0 = Group (auto), 1 = Manual
 *   manual_ids <str>   comma-separated 0-based track indices
 *   max_offset <float> max allowed shift in ms (default 100)
 *   bang               re-run UI bootstrap if UI is missing
 */

// ===================================================================
//  MAX JS BOILERPLATE
// ===================================================================
autowatch = 1;   // reload script when the file is saved
inlets    = 1;
outlets   = 1;   // outlet 0 → status display (message box)

// ===================================================================
//  STATE
// ===================================================================
var scopeMode   = "group";   // "group" | "manual"
var manualIds   = [];         // 0-based track indices for manual mode
var maxOffsetMs = 100.0;      // safety cap in milliseconds
var savedMarkers = {};        // clipPath → original start_marker (for reset)

// ===================================================================
//  SELF-BOOTSTRAPPING UI
// ===================================================================

function loadbang() {
	// Defer so the patcher is fully initialised
	var t = new Task(function () {
		bootstrapUI();
	}, this);
	t.schedule(500);
}

// Manual re-trigger: send a bang to re-run the bootstrap
function bang() {
	bootstrapUI();
}

function bootstrapUI() {
	var p = this.patcher;
	if (!p) {
		post("AudioSync: cannot access patcher — UI bootstrap skipped\n");
		return;
	}

	// ---- Idempotency: skip if UI was already created ----
	var alreadyDone = false;
	try {
		var check = p.getnamed("as_title");
		if (check) alreadyDone = true;
	} catch (e) { /* getnamed threw — object not found, that's fine */ }

	if (alreadyDone) {
		post("AudioSync: UI already bootstrapped\n");
		setStatus("Ready — click ANALYZE to align transients");
		return;
	}

	var me = this.box;   // the js object we're running inside
	if (!me) {
		post("AudioSync: cannot locate own box in patcher\n");
		return;
	}

	post("AudioSync: bootstrapping UI …\n");

	// ---------------------------------------------------------------
	//  Layout constants
	// ---------------------------------------------------------------
	// Patching coords  (Max editor)
	var PX  = 30;
	var PY_TITLE   = 15;
	var PY_CTRL    = 55;
	var PY_BTN     = 100;
	var PY_LMESS   = 140;
	var PY_ADAPT   = 180;
	var PY_BTNMSG  = 220;
	// PY_JS ≈ 270  (where the js object already lives)
	var PY_STATUS  = 320;

	// Presentation coords  (Live device view)
	var DW  = 390;          // device width
	var PR0 = 6;            // title row
	var PR1 = 30;           // controls row
	var PR2 = 60;           // buttons row
	var PR3 = 90;           // status row

	// ---------------------------------------------------------------
	//  Create objects
	// ---------------------------------------------------------------

	// ---- Title (presentation only) ----
	var title = p.newdefault(PX, PY_TITLE, "comment",
		"@text",  "AudioSync Transient Aligner",
		"@fontsize", 12, "@fontface", 1,
		"@presentation", 1,
		"@presentation_rect", 8, PR0, 250, 18,
		"@varname", "as_title");

	// ---- Scope ----
	var lblScope = p.newdefault(PX, PY_CTRL + 5, "comment",
		"@text", "Scope:",
		"@presentation", 1,
		"@presentation_rect", 8, PR1, 42, 18);

	var scopeMenu = p.newdefault(78, PY_CTRL, "umenu",
		"@presentation", 1,
		"@presentation_rect", 50, PR1 - 2, 80, 22);
	scopeMenu.message("append", "Group");
	scopeMenu.message("append", "Manual");

	// adapter: umenu index → "scope $1"
	var mScope = p.newdefault(78, PY_ADAPT, "message", "scope", "$1");

	// ---- Track IDs ----
	var lblIds = p.newdefault(178, PY_CTRL + 5, "comment",
		"@text", "IDs:",
		"@presentation", 1,
		"@presentation_rect", 140, PR1, 28, 18);

	var idsInput = p.newdefault(210, PY_CTRL, "textedit",
		"@presentation", 1,
		"@presentation_rect", 168, PR1 - 2, 90, 22);

	// adapter: text → "manual_ids $1"
	var mIds = p.newdefault(210, PY_ADAPT, "message", "manual_ids", "$1");

	// ---- Max-offset cap ----
	var lblOff = p.newdefault(315, PY_CTRL + 5, "comment",
		"@text", "Cap:",
		"@presentation", 1,
		"@presentation_rect", 268, PR1, 30, 18);

	var offsetNum = p.newdefault(345, PY_CTRL, "flonum",
		"@presentation", 1,
		"@presentation_rect", 296, PR1 - 2, 50, 22);

	var lblMs = p.newdefault(398, PY_CTRL + 5, "comment",
		"@text", "ms",
		"@presentation", 1,
		"@presentation_rect", 348, PR1, 22, 18);

	// adapter: float → "max_offset $1"
	var mOffset = p.newdefault(315, PY_ADAPT, "message", "max_offset", "$1");

	// loadmess: initialise the offset flonum to 100
	var lmOffset = p.newdefault(315, PY_LMESS, "loadmess", 100.);

	// ---- Buttons ----
	var btnAnalyze = p.newdefault(PX, PY_BTN, "textbutton",
		"@text", "ANALYZE", "@fontsize", 11, "@mode", 0,
		"@presentation", 1,
		"@presentation_rect", 8, PR2, 90, 28);

	var mAnalyze = p.newdefault(PX, PY_BTNMSG, "message", "analyze");

	var btnReset = p.newdefault(145, PY_BTN, "textbutton",
		"@text", "RESET", "@fontsize", 11, "@mode", 0,
		"@presentation", 1,
		"@presentation_rect", 106, PR2, 70, 28);

	var mReset = p.newdefault(145, PY_BTNMSG, "message", "reset");

	// ---- Status ----
	var lblStatus = p.newdefault(PX, PY_STATUS, "comment",
		"@text", "Status:", "@fontface", 1,
		"@presentation", 1,
		"@presentation_rect", 8, PR3, 48, 18);

	var statusMsg = p.newdefault(82, PY_STATUS, "message",
		"@presentation", 1,
		"@presentation_rect", 56, PR3, 324, 18);
	statusMsg.message("set", "Ready");

	// ---------------------------------------------------------------
	//  Connections
	// ---------------------------------------------------------------
	try {
		// Scope: umenu → "scope $1" → js
		p.connect(scopeMenu, 0, mScope, 0);
		p.connect(mScope,    0, me,     0);

		// IDs: textedit → "manual_ids $1" → js
		p.connect(idsInput, 0, mIds, 0);
		p.connect(mIds,     0, me,   0);

		// Analyze: textbutton → "analyze" → js
		p.connect(btnAnalyze, 0, mAnalyze, 0);
		p.connect(mAnalyze,   0, me,       0);

		// Reset: textbutton → "reset" → js
		p.connect(btnReset, 0, mReset, 0);
		p.connect(mReset,   0, me,     0);

		// Max-offset: flonum → "max_offset $1" → js
		p.connect(offsetNum, 0, mOffset, 0);
		p.connect(mOffset,   0, me,      0);

		// loadmess 100. → flonum  (initialise default)
		p.connect(lmOffset, 0, offsetNum, 0);

		// js outlet 0 → status message box
		p.connect(me, 0, statusMsg, 0);
	} catch (e) {
		post("AudioSync: wiring error — " + e + "\n");
	}

	// ---------------------------------------------------------------
	//  Patcher-level settings
	// ---------------------------------------------------------------
	try { p.message("setattr", "devicewidth", DW); } catch (e) {}
	try { p.message("setattr", "openinpresentation", 1); } catch (e) {}

	post("AudioSync: UI bootstrap complete — save the device (Cmd+S)\n");
	setStatus("Ready — click ANALYZE to align transients");
}

// ===================================================================
//  MESSAGE HANDLERS
// ===================================================================

function scope(val) {
	scopeMode = (val === 0 || val === "0" || val === "Group") ? "group" : "manual";
	setStatus("Scope: " + scopeMode);
}

function manual_ids() {
	var raw = arrayfromargs(arguments).join(" ");
	manualIds = parseIdString(raw);
	setStatus("Manual track indices: " + (manualIds.length ? manualIds.join(", ") : "(none)"));
}

function max_offset(ms) {
	var v = parseFloat(ms);
	if (!isNaN(v) && v > 0) {
		maxOffsetMs = v;
	}
}

// ===================================================================
//  ANALYZE — full pipeline
// ===================================================================

function analyze() {
	setStatus("Analyzing…");

	// 1) Discover target tracks
	var trackIds = discoverTracks();
	if (!trackIds || !trackIds.length) {
		setStatus("No tracks found (scope=" + scopeMode + "). Check group or manual IDs.");
		return;
	}

	// 2) Enumerate all audio clips on those tracks
	var allClips = [];
	for (var t = 0; t < trackIds.length; t++) {
		var clips = enumerateClips(trackIds[t]);
		for (var c = 0; c < clips.length; c++) {
			allClips.push(clips[c]);
		}
	}
	if (!allClips.length) {
		setStatus("No audio clips found on " + trackIds.length + " tracks.");
		return;
	}

	// 3) Pick reference track (highest peak clip gain)
	var refTrackId = pickReferenceTrack(allClips);

	// 4) Collect reference transient positions (sorted)
	var refPositions = [];
	for (var r = 0; r < allClips.length; r++) {
		if (allClips[r].trackId === refTrackId) {
			refPositions.push(allClips[r].transientPos);
		}
	}
	refPositions.sort(function (a, b) { return a - b; });

	if (!refPositions.length) {
		setStatus("Reference track has no usable clips.");
		return;
	}

	// 5) For each non-reference clip: find nearest ref transient, apply offset
	var bpm     = getTempo();
	var applied = 0;
	var skipped = 0;

	for (var i = 0; i < allClips.length; i++) {
		var ci = allClips[i];
		if (ci.trackId === refTrackId) continue;

		var nearest     = findClosest(refPositions, ci.transientPos);
		var offsetBeats = nearest - ci.transientPos;
		var offsetMs    = beatsToMs(offsetBeats, bpm);

		if (Math.abs(offsetMs) > maxOffsetMs) { skipped++; continue; }
		if (Math.abs(offsetBeats) < 0.00001)  continue;   // already aligned

		applyClipOffset(ci, offsetBeats);
		applied++;
	}

	setStatus("Aligned " + applied + " clip" + (applied !== 1 ? "s" : "") +
	          ", skipped " + skipped +
	          " (>" + maxOffsetMs + " ms). " +
	          allClips.length + " total, ref track id " + refTrackId);
}

// ===================================================================
//  RESET — restore original start_marker values
// ===================================================================

function reset() {
	var keys = Object.keys(savedMarkers);
	if (!keys.length) {
		setStatus("Nothing to reset.");
		return;
	}
	var restored = 0;
	for (var i = 0; i < keys.length; i++) {
		try {
			var clip = new LiveAPI(keys[i]);
			if (clip.id != 0) {
				clip.set("start_marker", savedMarkers[keys[i]]);
				restored++;
			}
		} catch (e) {
			post("AudioSync reset error [" + keys[i] + "]: " + e + "\n");
		}
	}
	savedMarkers = {};
	setStatus("Reset " + restored + " clip" + (restored !== 1 ? "s" : "") + " to original positions.");
}

// ===================================================================
//  TRACK DISCOVERY
// ===================================================================

function discoverTracks() {
	return (scopeMode === "manual")
		? resolveManualIndices(manualIds)
		: resolveGroupTracks();
}

function resolveManualIndices(indices) {
	var allIds = getAllTrackIds();
	var result = [];
	for (var i = 0; i < indices.length; i++) {
		var idx = indices[i];
		if (idx >= 0 && idx < allIds.length) {
			result.push(allIds[idx]);
		} else {
			post("AudioSync: track index " + idx + " out of range (0.." + (allIds.length - 1) + ")\n");
		}
	}
	return result;
}

function resolveGroupTracks() {
	var thisId = getThisTrackId();
	if (!thisId) {
		post("AudioSync: cannot locate this device's track\n");
		return [];
	}

	var track   = new LiveAPI("id " + thisId);
	var grouped = toInt(track.get("is_grouped"));
	var groupId = 0;

	if (grouped) {
		groupId = extractId(track.get("group_track"));
	} else {
		var foldable = toInt(track.get("is_foldable"));
		if (foldable) groupId = thisId;
	}

	if (!groupId) {
		post("AudioSync: track is not in a group — analysing only this track\n");
		return [thisId];
	}

	var allIds   = getAllTrackIds();
	var children = [];

	for (var i = 0; i < allIds.length; i++) {
		if (allIds[i] === groupId) continue;
		try {
			var t    = new LiveAPI("id " + allIds[i]);
			var gRef = t.get("group_track");
			if (extractId(gRef) === groupId) {
				children.push(allIds[i]);
			}
		} catch (e) { continue; }
	}

	return children.length ? children : [thisId];
}

// ===================================================================
//  CLIP ENUMERATION
// ===================================================================

function enumerateClips(trackId) {
	var arr = getArrangementClips(trackId);
	if (arr.length) return arr;
	return getSessionClips(trackId);
}

function getArrangementClips(trackId) {
	var results  = [];
	var trackIdx = getTrackIndex(trackId);
	if (trackIdx < 0) return results;

	try {
		var track = new LiveAPI("id " + trackId);
		var refs  = track.get("arrangement_clips");
		var ids   = extractIdList(refs);

		for (var i = 0; i < ids.length; i++) {
			try {
				var path = "live_set tracks " + trackIdx + " arrangement_clips " + i;
				var clip = new LiveAPI(path);
				if (!clip || clip.id == 0) continue;
				if (!toInt(clip.get("is_audio_clip"))) continue;

				var info = extractClipInfo(clip, trackId, path);
				if (info) results.push(info);
			} catch (e) {
				post("AudioSync: arrangement clip " + i + " error: " + e + "\n");
			}
		}
	} catch (e) {}
	return results;
}

function getSessionClips(trackId) {
	var results = [];
	try {
		var track    = new LiveAPI("id " + trackId);
		var slotRefs = track.get("clip_slots");
		var slotIds  = extractIdList(slotRefs);

		for (var i = 0; i < slotIds.length; i++) {
			try {
				var slot = new LiveAPI("id " + slotIds[i]);
				if (!toInt(slot.get("has_clip"))) continue;

				var clipRef = slot.get("clip");
				var clipId  = extractId(clipRef);
				if (!clipId) continue;

				var clip = new LiveAPI("id " + clipId);
				if (!toInt(clip.get("is_audio_clip"))) continue;

				var path = "id " + clipId;
				var info = extractClipInfo(clip, trackId, path);
				if (info) results.push(info);
			} catch (e) { continue; }
		}
	} catch (e) {}
	return results;
}

// ===================================================================
//  TRANSIENT EXTRACTION
// ===================================================================

function extractClipInfo(clip, trackId, clipPath) {
	var startMarker = toFloat(clip.get("start_marker"));
	var startTime   = toFloat(clip.get("start_time"));
	var gain        = toFloat(clip.get("gain"));
	var isWarped    = toInt(clip.get("warping"));

	// Default: use start_marker as first transient beat position
	var firstTransientBeat = startMarker;

	if (isWarped) {
		var markers = readWarpMarkers(clip);
		if (markers && markers.length > 0) {
			firstTransientBeat = markers[0].beat_time;
		}
	}

	// Absolute transient position in arrangement
	var transientPos = startTime + (firstTransientBeat - startMarker);

	return {
		trackId:      trackId,
		clipPath:     clipPath,
		clipId:       clip.id,
		arrPos:       startTime,
		startMarker:  startMarker,
		transientPos: transientPos,
		gain:         gain
	};
}

function readWarpMarkers(clip) {
	try {
		var raw = clip.get("warp_markers");
		if (!raw) return null;

		// String form — try Dict, then JSON.parse
		if (typeof raw === "string" && raw.length > 0) {
			try {
				var d  = new Dict(raw);
				var wm = d.get("warp_markers");
				if (wm) return normalizeMarkerEntries(wm);
			} catch (e1) {}
			try {
				var parsed = JSON.parse(raw);
				if (parsed && parsed.warp_markers) return normalizeMarkerEntries(parsed.warp_markers);
				if (Array.isArray(parsed)) return normalizeMarkerEntries(parsed);
			} catch (e2) {}
		}

		// Array form
		if (Array.isArray(raw)) {
			if (raw.length === 1 && typeof raw[0] === "string") {
				try {
					var d2  = new Dict(raw[0]);
					var wm2 = d2.get("warp_markers");
					if (wm2) return normalizeMarkerEntries(wm2);
				} catch (e3) {}
			}
			// Flat number pairs: [beat0, sample0, beat1, sample1, …]
			if (raw.length >= 2 && typeof raw[0] === "number") {
				var markers = [];
				for (var i = 0; i < raw.length - 1; i += 2) {
					markers.push({ beat_time: raw[i], sample_time: raw[i + 1] });
				}
				return markers.length ? markers : null;
			}
			return normalizeMarkerEntries(raw);
		}

		// Object form
		if (typeof raw === "object" && raw !== null) {
			if (raw.warp_markers) return normalizeMarkerEntries(raw.warp_markers);
		}

		return null;
	} catch (e) {
		return null;
	}
}

function normalizeMarkerEntries(entries) {
	if (!entries) return null;

	if (!Array.isArray(entries)) {
		try {
			if (typeof entries === "string") {
				var d    = new Dict(entries);
				entries  = [];
				var keys = d.getkeys();
				if (keys) {
					for (var k = 0; k < keys.length; k++) {
						entries.push(d.get(keys[k]));
					}
				}
			}
		} catch (e) { return null; }
	}
	if (!Array.isArray(entries)) return null;

	var result = [];
	for (var i = 0; i < entries.length; i++) {
		var e = entries[i];
		if (e && typeof e === "object") {
			var bt = parseFloat(e.beat_time);
			var st = parseFloat(e.sample_time);
			if (!isNaN(bt) && !isNaN(st)) {
				result.push({ beat_time: bt, sample_time: st });
			}
		}
	}
	return result.length ? result : null;
}

// ===================================================================
//  REFERENCE SELECTION  (highest peak clip gain)
// ===================================================================

function pickReferenceTrack(allClips) {
	var peakByTrack = {};
	for (var i = 0; i < allClips.length; i++) {
		var tid = allClips[i].trackId;
		var g   = allClips[i].gain;
		if (!(tid in peakByTrack) || g > peakByTrack[tid]) {
			peakByTrack[tid] = g;
		}
	}
	var bestId   = allClips[0].trackId;
	var bestGain = -1;
	var keys     = Object.keys(peakByTrack);
	for (var j = 0; j < keys.length; j++) {
		if (peakByTrack[keys[j]] > bestGain) {
			bestGain = peakByTrack[keys[j]];
			bestId   = parseInt(keys[j], 10);
		}
	}
	return bestId;
}

// ===================================================================
//  OFFSET APPLICATION
// ===================================================================

function applyClipOffset(clipInfo, offsetBeats) {
	try {
		var clip = new LiveAPI(clipInfo.clipPath);
		if (!clip || clip.id == 0) {
			clip = new LiveAPI("id " + clipInfo.clipId);
		}

		// Preserve original for reset
		var key = clipInfo.clipPath || ("id_" + clipInfo.clipId);
		if (!(key in savedMarkers)) {
			savedMarkers[key] = clipInfo.startMarker;
		}

		// Shift start_marker by -offset so audio plays earlier/later
		var newMarker = clipInfo.startMarker - offsetBeats;
		clip.set("start_marker", newMarker);
	} catch (e) {
		post("AudioSync: offset error — " + e + "\n");
	}
}

// ===================================================================
//  CLOSEST-MATCH  (binary search on sorted array)
// ===================================================================

function findClosest(sorted, value) {
	if (!sorted.length) return value;
	if (sorted.length === 1) return sorted[0];

	var lo = 0, hi = sorted.length - 1;
	while (lo < hi - 1) {
		var mid = Math.floor((lo + hi) / 2);
		if (sorted[mid] <= value) lo = mid;
		else hi = mid;
	}
	return (Math.abs(sorted[lo] - value) <= Math.abs(sorted[hi] - value))
		? sorted[lo] : sorted[hi];
}

// ===================================================================
//  LIVE API UTILITIES
// ===================================================================

function getTempo() {
	try {
		var s = new LiveAPI("live_set");
		var t = toFloat(s.get("tempo"));
		return t > 0 ? t : 120;
	} catch (e) { return 120; }
}

function getAllTrackIds() {
	var s = new LiveAPI("live_set");
	return extractIdList(s.get("tracks"));
}

function getTrackIndex(trackId) {
	var ids = getAllTrackIds();
	for (var i = 0; i < ids.length; i++) {
		if (ids[i] === trackId) return i;
	}
	return -1;
}

function getThisTrackId() {
	try {
		var d = new LiveAPI("this_device");
		return extractId(d.get("canonical_parent"));
	} catch (e) { return 0; }
}

function beatsToMs(beats, bpm) {
	return (beats / bpm) * 60000.0;
}

// ===================================================================
//  LOW-LEVEL HELPERS
// ===================================================================

function extractId(val) {
	if (val == null) return 0;
	if (typeof val === "number") return val;
	if (Array.isArray(val)) {
		for (var i = 0; i < val.length; i++) {
			if (val[i] === "id" && typeof val[i + 1] === "number")
				return val[i + 1];
		}
		if (val.length === 1 && typeof val[0] === "number") return val[0];
	}
	return 0;
}

function extractIdList(val) {
	var ids = [];
	if (!Array.isArray(val)) return ids;
	for (var i = 0; i < val.length; i++) {
		if (val[i] === "id" && typeof val[i + 1] === "number")
			ids.push(val[i + 1]);
	}
	return ids;
}

function toInt(val) {
	if (Array.isArray(val)) val = val[0];
	var n = parseInt(val, 10);
	return isNaN(n) ? 0 : n;
}

function toFloat(val) {
	if (Array.isArray(val)) val = val[0];
	var n = parseFloat(val);
	return isNaN(n) ? 0.0 : n;
}

function parseIdString(s) {
	if (!s) return [];
	var parts  = s.toString().split(/[,\s]+/);
	var result = [];
	for (var i = 0; i < parts.length; i++) {
		var n = parseInt(parts[i], 10);
		if (!isNaN(n)) result.push(n);
	}
	return result;
}

function setStatus(msg) {
	outlet(0, "set", msg);
	post("AudioSync: " + msg + "\n");
}
