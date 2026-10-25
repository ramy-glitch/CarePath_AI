/** Synthetic numbers for the on-screen journey. No name, NHS number, or date of birth. */
export const EXAMPLE_REPORT = {
  results: [
    {
      testName: "Neutrophils",
      value: 1.6,
      unit: "x10^9/L",
      referenceRange: { low: 1.9, high: 8.0 },
      flag: "low",
    },
    {
      testName: "White blood cells",
      value: 3.8,
      unit: "x10^9/L",
      referenceRange: { low: 4.0, high: 11.0 },
      flag: "low",
    },
  ],
  reviewRequired: true,
};
