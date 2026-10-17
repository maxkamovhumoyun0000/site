const test = require("node:test");
const assert = require("node:assert/strict");
const { parseLiveRoomDate } = require("../app/ui/live-room-date.js");

test("timezone-free database timestamps are interpreted as UTC", () => {
  const date = parseLiveRoomDate("2026-10-17T06:00:38.510774");
  assert.equal(date.toISOString(), "2026-10-17T06:00:38.510Z");
});

test("timestamps that already have an offset keep that offset", () => {
  const date = parseLiveRoomDate("2026-10-17T11:00:38+05:00");
  assert.equal(date.toISOString(), "2026-10-17T06:00:38.000Z");
});
