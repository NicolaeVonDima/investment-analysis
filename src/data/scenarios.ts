import { Scenario } from '../types';

export const scenarios: Scenario[] = [
  {
    name: 'Pessimistic',
    inflation: 0.045,
    assetReturns: {
      vwce: 0.04,
      tvbetetf: 0.03,
      vgwd: 0.02,
      vgwdYield: 0.025,
      fidelis: 0.05
    },
    trimRules: {
      vwce: {
        enabled: false,
        threshold: 0.0
      },
      tvbetetf: {
        enabled: false,
        threshold: 0.0
      },
      vgwd: {
        enabled: false,
        threshold: 0.0
      }
    },
    fidelisCap: 24000
  },
  {
    name: 'Average',
    inflation: 0.03,
    assetReturns: {
      vwce: 0.07,
      tvbetetf: 0.08,
      vgwd: 0.05,
      vgwdYield: 0.03,
      fidelis: 0.06
    },
    trimRules: {
      vwce: {
        enabled: true,
        threshold: 0.0  // Changed from 0.04 to 0.0 to generate 4% trim (7% - 3% - 0%)
      },
      tvbetetf: {
        enabled: true,
        threshold: 0.0  // Changed from 0.06 to 0.0 to generate 5% trim (8% - 3% - 0%)
      },
      vgwd: {
        enabled: false,
        threshold: 0.0
      }
    },
    fidelisCap: 24000
  },
  {
    name: 'Optimistic',
    inflation: 0.02,
    assetReturns: {
      vwce: 0.10,
      tvbetetf: 0.12,
      vgwd: 0.07,
      vgwdYield: 0.035,
      fidelis: 0.065
    },
    trimRules: {
      vwce: {
        enabled: true,
        threshold: 0.04
      },
      tvbetetf: {
        enabled: true,
        threshold: 0.06
      },
      vgwd: {
        enabled: false,
        threshold: 0.0
      }
    },
    fidelisCap: 24000
  }
];

export const defaultScenario = scenarios[1]; // Average
