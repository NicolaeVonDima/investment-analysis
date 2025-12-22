import React from 'react';
import { Portfolio } from '../../types';

interface RulesConfigProps {
  rules: Portfolio['rules'];
  onChange: (rules: Portfolio['rules']) => void;
}

export default function RulesConfig({ rules, onChange }: RulesConfigProps) {
  // Currently no portfolio-specific rules to configure
  // All settings are now in the scenario
  return (
    <div className="text-xs text-gray-500 italic">
      All portfolio rules are configured in the scenario settings above.
    </div>
  );
}

