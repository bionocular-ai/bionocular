/**
 * Tools that produce citable data. `store_finding.sourceTool` is an enum over
 * these, so a saved finding can never name a tool that does not exist - the
 * old free-text field still suggested `search_clinical_trials`, deleted months
 * before this file was written.
 */
export const DATA_TOOL_NAMES = ['query_proprietary_data'] as const;

export type DataToolName = typeof DATA_TOOL_NAMES[number];
