function parseLiveRoomDate(value) {
  if (value == null || String(value).trim() === "") return null;

  const raw = String(value).trim();
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw);
  const normalized = raw.includes(" ") ? raw.replace(" ", "T") : raw;
  const date = new Date(hasTimezone ? normalized : `${normalized}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

module.exports = { parseLiveRoomDate };
