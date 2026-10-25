/** The confirmation checkbox never leaves the browser. Storage happens only after it is ticked. */

export function flagForReport(value, range) {
  if (!range || typeof range.low !== "number" || typeof range.high !== "number") return "unknown";
  if (!(range.low < range.high)) return "unknown";
  if (value < range.low) return "low";
  if (value > range.high) return "high";
  return "normal";
}

export function rowFromFields(fields) {
  const testName = fields.testName.trim();
  const valueBlank = fields.value === "" || fields.value == null;
  const value = Number(fields.value);
  const unit = fields.unit.trim();
  const lowBlank = fields.low === "" || fields.low == null;
  const highBlank = fields.high === "" || fields.high == null;
  let referenceRange = null;
  if (!lowBlank || !highBlank) {
    const low = Number(fields.low);
    const high = Number(fields.high);
    if (!Number.isFinite(low) || !Number.isFinite(high) || !(low < high)) {
      return { error: "Each range needs a lower number and a higher number." };
    }
    referenceRange = { low, high };
  }
  if (!testName || !unit || valueBlank || !Number.isFinite(value)) {
    return { error: "Each row needs a test name, a number, and a unit." };
  }
  return {
    testName,
    value,
    unit,
    referenceRange,
    flag: flagForReport(value, referenceRange),
  };
}

export function labFromRows(rows) {
  if (!rows.length) return { error: "CarePath needs at least one result." };
  return { results: rows, reviewRequired: true };
}

export function mayStore(checked) {
  return checked === true;
}
