/** Same sentence the server returns when a chat turn is not covered. */
export const FIXED_MESSAGE = "This result is not covered here. Contact your GP or NHS 111.";

/** Rule for a critically high potassium. Not chosen by the explanation model. */
export const URGENT_MESSAGE = "Contact your GP today or call NHS 111.";

export const UNDERAGE_MESSAGE =
  "CarePath does not explain blood-test reports for anyone under 18. Please talk to a parent, carer, or your GP.";

export const UNREADABLE_MESSAGE =
  "CarePath could not read this photo clearly, so it will not guess. Please upload a clearer copy.";

export const PDF_MESSAGE =
  "This prototype reads a PNG or JPEG photo of the report. The PDF was not uploaded.";
