import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Portfolio, Scenario, ChartType } from './types';
import { scenarios, defaultScenario } from './data/scenarios';
import { portfolioTemplates, portfolioColors } from './data/templates';
import { useSimulation } from './hooks/useSimulation';
import { saveData, loadData } from './services/api';
import Header from './components/Header';
import ScenarioSelector from './components/ScenarioSelector';
import PortfolioCard from './components/PortfolioBuilder/PortfolioCard';
import CapitalChart from './components/Charts/CapitalChart';
import IncomeChart from './components/Charts/IncomeChart';
import BreakdownChart from './components/Charts/BreakdownChart';
import AllocationChart from './components/Charts/AllocationChart';
import ComparisonTable from './components/ComparisonTable';
import { formatCurrency } from './utils/formatters';
import './App.css';

function App() {
  const [globalInvestment, setGlobalInvestment] = useState(675000);
  const [portfolios, setPortfolios] = useState<Portfolio[]>(() => {
    // Initialize with templates
    return portfolioTemplates.map((template, index) => ({
      ...template,
      id: `portfolio-${index + 1}`,
      color: portfolioColors[index],
      capital: globalInvestment,
      goal: template.goal
    }));
  });
  
  const [scenariosState, setScenariosState] = useState<Scenario[]>(scenarios);
  const [selectedScenario, setSelectedScenario] = useState<Scenario>(defaultScenario);
  const [customScenario, setCustomScenario] = useState<Scenario | null>(null);
  const [selectedChart, setSelectedChart] = useState<ChartType>('capital');
  const [selectedPortfolioForBreakdown, setSelectedPortfolioForBreakdown] = useState<string | null>(null);
  const [showReal, setShowReal] = useState(true);
  const [isLoading, setIsLoading] = useState(true);

  // Load data on mount
  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const data = await loadData();
        if (data.portfolios && data.portfolios.length > 0) {
          // Merge loaded portfolios with template data to ensure missing fields are populated
          const mergedPortfolios = data.portfolios.map((loadedPortfolio: Portfolio) => {
            // Find matching template by name
            const template = portfolioTemplates.find(t => t.name === loadedPortfolio.name);
            if (template) {
              // Merge template data with loaded data, prioritizing loaded data
              return {
                ...template,
                ...loadedPortfolio,
                // Preserve loaded values but fill in missing template fields
                // Use nullish coalescing to handle null, undefined, and empty objects
                riskLabel: loadedPortfolio.riskLabel ?? template.riskLabel,
                horizon: loadedPortfolio.horizon ?? template.horizon,
                overperformStrategy: loadedPortfolio.overperformStrategy ?? template.overperformStrategy,
                goal: loadedPortfolio.goal ?? template.goal,
                // Preserve loaded allocation and rules
                allocation: loadedPortfolio.allocation,
                rules: loadedPortfolio.rules,
                capital: loadedPortfolio.capital
              };
            }
            return loadedPortfolio;
          });
          
          // Sort portfolios to match template order and update colors based on template position
          const sortedPortfolios = portfolioTemplates
            .map((template, index) => {
              const portfolio = mergedPortfolios.find(p => p.name === template.name);
              if (portfolio) {
                return {
                  ...portfolio,
                  color: portfolioColors[index] // Update color based on template position
                };
              }
              return null;
            })
            .filter((p): p is Portfolio => p !== null);
          
          // Add any portfolios not in templates at the end
          const templateNames = portfolioTemplates.map(t => t.name);
          const extraPortfolios = mergedPortfolios.filter(p => !templateNames.includes(p.name));
          
          setPortfolios([...sortedPortfolios, ...extraPortfolios]);
          setGlobalInvestment(data.portfolios[0]?.capital || 675000);
        }
        if (data.scenarios && data.scenarios.length > 0) {
          // Update scenarios state with loaded data
          const loadedScenarios = data.scenarios as Scenario[];
          setScenariosState(loadedScenarios);
          
          // Find default scenario or use first one
          const defaultSc = loadedScenarios.find(s => s.name === (data.default_scenario_id || 'Average')) || loadedScenarios[0];
          if (defaultSc) {
            setSelectedScenario(defaultSc);
          }
        }
      } catch (error) {
        console.warn('Could not load data from backend, using defaults:', error);
      } finally {
        setIsLoading(false);
      }
    };
    loadInitialData();
  }, []);

  // Auto-save when data changes (debounced)
  const saveToBackend = useCallback(async () => {
    if (isLoading) return;
    
    try {
      const activeScenario = customScenario || selectedScenario;
      // Only save if scenario is valid
      if (!activeScenario || !activeScenario.assetReturns) {
        return;
      }
      // Include all preset scenarios plus the active (custom) one
      const allScenarios = [
        activeScenario,
        ...scenariosState.filter(s => s.name !== activeScenario.name)
      ];
      await saveData({
        portfolios,
        scenarios: allScenarios,
        default_scenario_id: activeScenario.name
      });
    } catch (error) {
      console.error('Error saving data:', error);
    }
  }, [portfolios, selectedScenario, customScenario, scenariosState, isLoading]);

  // Debounced auto-save
  useEffect(() => {
    if (isLoading) return;
    const timer = setTimeout(() => {
      saveToBackend();
    }, 1000); // Save 1 second after last change
    return () => clearTimeout(timer);
  }, [portfolios, selectedScenario, customScenario, saveToBackend, isLoading]);

  // Update all portfolios when global investment changes
  useEffect(() => {
    setPortfolios(prev => prev.map(p => ({ ...p, capital: globalInvestment })));
  }, [globalInvestment]);

  const activeScenario = customScenario || selectedScenario;
  
  // Safety check: ensure scenario has required fields
  const safeScenario: Scenario = activeScenario && activeScenario.assetReturns ? activeScenario : defaultScenario;
  
  const simulationResults = useSimulation(portfolios, safeScenario, 35);

  const handleUpdatePortfolio = (updated: Portfolio) => {
    setPortfolios(portfolios.map(p => p.id === updated.id ? updated : p));
  };

  const handleScenarioUpdate = (scenario: Scenario) => {
    setCustomScenario(scenario);
  };

  const handleScenarioSelect = (scenario: Scenario) => {
    setSelectedScenario(scenario);
    setCustomScenario(null);
  };

  const handleScenarioSave = useCallback(async (scenarioToSave: Scenario) => {
    // Always use the currently active scenario (which may have been edited) if it matches
    const activeScenario = customScenario || selectedScenario;
    
    console.log('Save button clicked for:', scenarioToSave.name);
    console.log('Active scenario:', activeScenario.name);
    console.log('Has customScenario:', !!customScenario);
    console.log('Active scenario assetReturns.vwce:', activeScenario.assetReturns?.vwce);
    console.log('Scenario to save assetReturns.vwce:', scenarioToSave.assetReturns?.vwce);
    
    // Use the active scenario if it matches the one being saved (it contains the edits)
    const scenarioToSave_ = 
      (activeScenario.name === scenarioToSave.name) 
        ? activeScenario 
        : scenarioToSave;
    
    if (!scenarioToSave_ || !scenarioToSave_.assetReturns) {
      console.warn('Cannot save: scenario is invalid', scenarioToSave_);
      return;
    }
    
    try {
      console.log('Saving scenario with data:', {
        name: scenarioToSave_.name,
        vwce: scenarioToSave_.assetReturns.vwce,
        inflation: scenarioToSave_.inflation
      });
      
      // Build the scenarios array with the updated scenario
      const scenarioIndex = scenariosState.findIndex(s => s.name === scenarioToSave_.name);
      let updatedScenarios: Scenario[];
      
      if (scenarioIndex >= 0) {
        // Update the existing scenario in the array
        updatedScenarios = [...scenariosState];
        updatedScenarios[scenarioIndex] = scenarioToSave_;
      } else {
        // Add new scenario (custom scenario)
        updatedScenarios = [
          scenarioToSave_,
          ...scenariosState.filter(s => s.name !== scenarioToSave_.name)
        ];
      }
      
      await saveData({
        portfolios,
        scenarios: updatedScenarios,
        default_scenario_id: scenarioToSave_.name
      });
      
      console.log(`✓ Successfully saved scenario: ${scenarioToSave_.name}`);
      
      // Update scenarios state with the saved version
      setScenariosState(updatedScenarios);
      
      // Update state to reflect the saved version
      setSelectedScenario(scenarioToSave_);
      setCustomScenario(null);
    } catch (error) {
      console.error('Error saving scenario:', error);
      throw error; // Re-throw so the button can show error state
    }
  }, [portfolios, selectedScenario, customScenario, scenariosState]);

  const selectedBreakdownResult = useMemo(() => {
    if (!selectedPortfolioForBreakdown) return null;
    return simulationResults.find(r => r.portfolioId === selectedPortfolioForBreakdown) || null;
  }, [simulationResults, selectedPortfolioForBreakdown]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-lg text-gray-600">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <div className="container mx-auto px-4 py-6">
        {/* Global Investment Amount */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <label className="block text-lg font-semibold text-gray-800 mb-2">
            Investment Amount
          </label>
          <p className="text-sm text-gray-600 mb-4">
            Set the total amount you want to invest. This will be applied to all portfolios for comparison.
          </p>
          <div className="flex items-center gap-4">
            <input
              type="number"
              value={globalInvestment}
              onChange={(e) => setGlobalInvestment(parseFloat(e.target.value) || 0)}
              className="px-4 py-2 border-2 border-primary rounded-lg text-lg font-semibold focus:outline-none focus:ring-2 focus:ring-primary w-48 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              min="0"
              step="1000"
            />
            <span className="text-lg font-medium text-gray-700">
              = {formatCurrency(globalInvestment)}
            </span>
          </div>
        </div>

        {/* Scenario Selector */}
        <div className="mb-6">
          <ScenarioSelector
            scenarios={scenariosState}
            selectedScenario={safeScenario}
            onSelect={handleScenarioSelect}
            onUpdate={handleScenarioUpdate}
            onSave={handleScenarioSave}
          />
        </div>

        {/* Portfolios in 3 Columns */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          {portfolios.map(portfolio => {
            const evolutionData = simulationResults.find(r => r.portfolioId === portfolio.id)?.years;
            return (
              <PortfolioCard
                key={portfolio.id}
                portfolio={portfolio}
                onUpdate={handleUpdatePortfolio}
                evolutionData={evolutionData}
                showReal={showReal}
              />
            );
          })}
        </div>

        {/* Charts Section */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Detailed Analysis</h2>
          
          {/* Chart Type Selector */}
          <div className="mb-4">
            <div className="flex flex-wrap gap-2 mb-4">
              <button
                onClick={() => setSelectedChart('capital')}
                className={`px-4 py-2 rounded-md font-medium ${
                  selectedChart === 'capital'
                    ? 'bg-primary text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Capital Growth
              </button>
              <button
                onClick={() => setSelectedChart('income')}
                className={`px-4 py-2 rounded-md font-medium ${
                  selectedChart === 'income'
                    ? 'bg-primary text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Monthly Income
              </button>
              <button
                onClick={() => setSelectedChart('breakdown')}
                className={`px-4 py-2 rounded-md font-medium ${
                  selectedChart === 'breakdown'
                    ? 'bg-primary text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Income Breakdown
              </button>
              <button
                onClick={() => setSelectedChart('allocation')}
                className={`px-4 py-2 rounded-md font-medium ${
                  selectedChart === 'allocation'
                    ? 'bg-primary text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Asset Allocation
              </button>
            </div>
            
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={showReal}
                  onChange={(e) => setShowReal(e.target.checked)}
                  className="w-4 h-4 text-primary border-gray-300 rounded focus:ring-primary"
                />
                <span className="text-sm text-gray-700">Show Real (Inflation-Adjusted) Values</span>
              </label>
            </div>

            {(selectedChart === 'breakdown' || selectedChart === 'allocation') && (
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Portfolio:
                </label>
                <select
                  value={selectedPortfolioForBreakdown || ''}
                  onChange={(e) => setSelectedPortfolioForBreakdown(e.target.value || null)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary max-w-xs"
                >
                  <option value="">-- Select --</option>
                  {portfolios.map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Chart Display */}
          <div className="mt-6">
            {selectedChart === 'capital' && (
              <CapitalChart results={simulationResults} showReal={showReal} />
            )}
            {selectedChart === 'income' && (
              <IncomeChart results={simulationResults} showReal={showReal} />
            )}
            {selectedChart === 'breakdown' && (
              <BreakdownChart result={selectedBreakdownResult} showReal={showReal} />
            )}
            {selectedChart === 'allocation' && (
              <AllocationChart result={selectedBreakdownResult} />
            )}
          </div>
        </div>

        {/* Comparison Table */}
        <ComparisonTable results={simulationResults} />
      </div>
    </div>
  );
}

export default App;
