import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Portfolio, Scenario, ChartType, FamilyMember, YearResult } from './types';
import { scenarios, defaultScenario } from './data/scenarios';
import { portfolioTemplates, portfolioColors } from './data/templates';
import { useSimulation } from './hooks/useSimulation';
import { saveData, loadData } from './services/api';
import { useAuth } from './contexts/AuthContext';
import Header from './components/Header';
import ScenarioSelector from './components/ScenarioSelector';
import PortfolioCard from './components/PortfolioBuilder/PortfolioCard';
import FamilyTotalCard from './components/PortfolioBuilder/FamilyTotalCard';
import FamilyMembersManager from './components/FamilyMembersManager';
import CapitalChart from './components/Charts/CapitalChart';
import IncomeChart from './components/Charts/IncomeChart';
import BreakdownChart from './components/Charts/BreakdownChart';
import AllocationChart from './components/Charts/AllocationChart';
import Login from './components/Login';
import Register from './components/Register';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import AdminPanel from './components/AdminPanel';
import { formatCurrency } from './utils/formatters';
import './App.css';

function PortfolioApp() {
  // Initialize with default family member (empty name will default to "Owner Portfolio")
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([
    { id: 'default-1', name: '', amount: 675000, displayOrder: 0, color: '#FF6B6B' }
  ]);
  
  // Calculate total investment from family members
  const totalInvestment = useMemo(() => {
    return familyMembers.reduce((sum, member) => sum + member.amount, 0);
  }, [familyMembers]);

  // Helper function to create member portfolio
  const createMemberPortfolio = (member: FamilyMember, existingPortfolio?: Portfolio): Portfolio => {
    // Use "Owner Portfolio" as default name if member name is empty
    const memberDisplayName = member.name.trim() || 'Owner Portfolio';
    const portfolioName = `${memberDisplayName}'s Portfolio`;
    // Use member's color if set, otherwise fall back to default colors
    const defaultColors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F'];
    const colorIndex = (member.displayOrder || 0) % defaultColors.length;
    const memberColor = member.color || defaultColors[colorIndex];
    
    return {
      id: existingPortfolio?.id || `member-portfolio-${member.id}`,
      name: portfolioName,
      color: existingPortfolio?.color || memberColor,
      capital: member.amount, // Always use member's current amount
      goal: `Portfolio allocation for ${memberDisplayName}`,
      riskLabel: 'Risk: Custom',
      horizon: 'Current',
      selectedStrategy: existingPortfolio?.selectedStrategy, // Preserve selected strategy
      allocation: existingPortfolio?.allocation || {
        vwce: 0,
        tvbetetf: 0,
        ernx: 0,
        ayeg: 0,
        fidelis: 0
      },
      rules: existingPortfolio?.rules || {
        tvbetetfConditional: false
      }
    };
  };

  // Initialize portfolios with strategic templates only (no Current Allocation)
  const strategicTemplates = portfolioTemplates.filter(t => t.name !== 'Current Allocation');
  const [portfolios, setPortfolios] = useState<Portfolio[]>(() => {
    // Start with strategic portfolios
    const strategic = strategicTemplates.map((template, index) => ({
      ...template,
      id: `portfolio-${index + 1}`,
      color: portfolioColors[index],
      capital: totalInvestment,
      goal: template.goal
    }));
    // Add member portfolios
    const memberPortfolios = familyMembers.map(member => createMemberPortfolio(member));
    return [...strategic, ...memberPortfolios];
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
        // Always ensure all templates are present
        const loadedPortfolioMap = new Map<string, Portfolio>();
        if (data.portfolios && data.portfolios.length > 0) {
          // Merge loaded portfolios with template data to ensure missing fields are populated
          data.portfolios.forEach((loadedPortfolio: Portfolio) => {
            // Migrate wqdv to ayeg if present
            const migratedAllocation: any = { ...loadedPortfolio.allocation };
            if ('wqdv' in migratedAllocation && !('ayeg' in migratedAllocation)) {
              migratedAllocation.ayeg = migratedAllocation.wqdv;
              delete migratedAllocation.wqdv;
            }
            
            // Find matching template by name
            const template = portfolioTemplates.find(t => t.name === loadedPortfolio.name);
            if (template) {
              // Merge template data with loaded data, prioritizing loaded data
              loadedPortfolioMap.set(loadedPortfolio.name, {
                ...template,
                ...loadedPortfolio,
                // Preserve loaded values but fill in missing template fields
                // Use nullish coalescing to handle null, undefined, and empty objects
                riskLabel: loadedPortfolio.riskLabel ?? template.riskLabel,
                horizon: loadedPortfolio.horizon ?? template.horizon,
                overperformStrategy: loadedPortfolio.overperformStrategy ?? template.overperformStrategy,
                goal: loadedPortfolio.goal ?? template.goal,
                // Use migrated allocation
                allocation: migratedAllocation,
                rules: loadedPortfolio.rules,
                capital: loadedPortfolio.capital
              });
            } else {
              loadedPortfolioMap.set(loadedPortfolio.name, {
                ...loadedPortfolio,
                allocation: migratedAllocation
              });
            }
          });
        }
        
        // Load family members from database first
        let loadedFamilyMembers: FamilyMember[] = [];
        if (data.familyMembers && data.familyMembers.length > 0) {
          // Sort by display_order to ensure correct order
          loadedFamilyMembers = [...data.familyMembers].sort((a, b) => (a.displayOrder || 0) - (b.displayOrder || 0));
          setFamilyMembers(loadedFamilyMembers);
        } else {
          // Migration: Recover family members from existing member portfolios
          const memberPortfoliosFromDB = data.portfolios?.filter((p: Portfolio) => 
            p.name.endsWith("'s Portfolio")
          ) || [];
          
          if (memberPortfoliosFromDB.length > 0) {
            // Extract family member info from portfolio names and IDs
            // Sort portfolios by name to ensure consistent order, then assign display_order
            const sortedPortfolios = [...memberPortfoliosFromDB].sort((a, b) => a.name.localeCompare(b.name));
            loadedFamilyMembers = sortedPortfolios.map((portfolio: Portfolio, index: number) => {
              // Extract member name from portfolio name (e.g., "Liana's Portfolio" -> "Liana")
              const memberName = portfolio.name.replace("'s Portfolio", "").trim();
              // Extract member ID from portfolio ID (e.g., "member-portfolio-member-1766493269405" -> "member-1766493269405")
              const memberId = portfolio.id.replace("member-portfolio-", "");
              
              // If this is "Owner Portfolio" or has default-1 id, it should be first (displayOrder 0)
              const isDefault = memberId === 'default-1' || memberName === "Owner Portfolio";
              
              return {
                id: memberId,
                name: memberName === "Owner Portfolio" ? "" : memberName,
                amount: portfolio.capital,
                displayOrder: isDefault ? 0 : index + 1
              };
            });
            // Sort by displayOrder to ensure first member is at index 0
            loadedFamilyMembers.sort((a, b) => (a.displayOrder || 0) - (b.displayOrder || 0));
            console.log('Recovered family members from portfolios:', loadedFamilyMembers);
            setFamilyMembers(loadedFamilyMembers);
          } else {
            // Fallback: Create default family member from portfolio capital if no members exist
            const loadedCapital = data.portfolios && data.portfolios.length > 0 
              ? data.portfolios[0].capital 
              : 675000;
            loadedFamilyMembers = [
              { id: 'default-1', name: '', amount: loadedCapital, displayOrder: 0, color: '#FF6B6B' } // Empty name defaults to "Owner Portfolio"
            ];
            setFamilyMembers(loadedFamilyMembers);
          }
        }

        // Separate strategic portfolios from member portfolios
        const strategicPortfolioNames = strategicTemplates.map(t => t.name);
        const loadedStrategicPortfolios: Portfolio[] = [];
        const loadedMemberPortfolios: Portfolio[] = [];
        
        data.portfolios.forEach((p: Portfolio) => {
          if (strategicPortfolioNames.includes(p.name)) {
            loadedStrategicPortfolios.push(p);
          } else if (p.name.endsWith("'s Portfolio")) {
            loadedMemberPortfolios.push(p);
          }
        });

        // Sort strategic portfolios to match template order
        const sortedStrategicPortfolios = strategicTemplates
          .map((template, index) => {
            const existingPortfolio = loadedStrategicPortfolios.find(p => p.name === template.name);
            if (existingPortfolio) {
              return {
                ...existingPortfolio,
                color: portfolioColors[index],
                capital: totalInvestment // Strategic portfolios use total investment
              };
            } else {
              return {
                ...template,
                id: `portfolio-${index + 1}`,
                color: portfolioColors[index],
                capital: totalInvestment
              };
            }
          });

        // Sort family members by display_order to maintain order
        const sortedFamilyMembers = [...loadedFamilyMembers].sort((a, b) => (a.displayOrder || 0) - (b.displayOrder || 0));
        
        // Create/update member portfolios from family members in display_order
        const memberPortfolios = sortedFamilyMembers.map(member => {
          // Find existing portfolio by member ID (most reliable)
          const existingPortfolio = loadedMemberPortfolios.find(p => 
            p.id === `member-portfolio-${member.id}`
          );
          
          // If member doesn't have a color but portfolio does, migrate the color to the member
          if (!member.color && existingPortfolio?.color) {
            member.color = existingPortfolio.color;
          }
          
          // Create portfolio with current member data (name and amount)
          const portfolio = createMemberPortfolio(member, existingPortfolio);
          
          // Preserve allocation and rules from existing portfolio if it exists
          // But always use member's color if set
          if (existingPortfolio) {
            portfolio.allocation = existingPortfolio.allocation;
            portfolio.rules = existingPortfolio.rules;
          }
          // Update color from member if member has a color set
          if (member.color) {
            portfolio.color = member.color;
          }
          
          return portfolio;
        });
        
        // Update family members with migrated colors
        if (memberPortfolios.some((p, idx) => sortedFamilyMembers[idx] && !sortedFamilyMembers[idx].color && p.color)) {
          const updatedMembers = sortedFamilyMembers.map((member, idx) => {
            const portfolio = memberPortfolios[idx];
            if (!member.color && portfolio && portfolio.id === `member-portfolio-${member.id}`) {
              return { ...member, color: portfolio.color };
            }
            return member;
          });
          setFamilyMembers(updatedMembers);
        }

        // Ensure we always have both strategic and member portfolios
        const allPortfolios = [...sortedStrategicPortfolios, ...memberPortfolios];
        setPortfolios(allPortfolios);
        if (data.scenarios && data.scenarios.length > 0) {
          // Migrate scenarios: convert wqdv to ayeg
          const migratedScenarios = (data.scenarios as Scenario[]).map((scenario: any) => {
            // Migrate assetReturns
            if (scenario.assetReturns || scenario.asset_returns) {
              const assetReturns = scenario.assetReturns || scenario.asset_returns;
              if ('wqdv' in assetReturns && !('ayeg' in assetReturns)) {
                assetReturns.ayeg = assetReturns.wqdv;
                assetReturns.ayegYield = assetReturns.wqdvYield;
                delete assetReturns.wqdv;
                delete assetReturns.wqdvYield;
              }
            }
            // Migrate trimRules
            if (scenario.trimRules || scenario.trim_rules) {
              const trimRules = scenario.trimRules || scenario.trim_rules;
              if (trimRules.wqdv && !trimRules.ayeg) {
                trimRules.ayeg = trimRules.wqdv;
                delete trimRules.wqdv;
              }
            }
            return scenario;
          });
          
          // Update scenarios state with loaded data, sorted in correct order
          const loadedScenarios = migratedScenarios.sort((a, b) => {
            // Define order: Pessimistic, Average, Optimistic
            const order: Record<string, number> = {
              'Pessimistic': 1,
              'Average': 2,
              'Optimistic': 3
            };
            return (order[a.name] || 999) - (order[b.name] || 999);
          });
          setScenariosState(loadedScenarios);
          
          // Find default scenario or use first one
          const defaultSc = loadedScenarios.find(s => s.name === (data.default_scenario_id || 'Average')) || loadedScenarios[0];
          if (defaultSc) {
            setSelectedScenario(defaultSc);
          }
        }
      } catch (error: any) {
        // Log error but don't render it - just use defaults
        const errorMsg = error?.response?.data?.detail || error?.message || 'Unknown error';
        console.warn('Could not load data from backend, using defaults:', typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
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
      // Update strategic portfolios to use total investment, sync member portfolios with their member's amount
      const portfoliosToSave = portfolios.map(p => {
        if (p.name.endsWith("'s Portfolio")) {
          // Member portfolio - find matching family member and use their current amount
          const memberId = p.id.replace('member-portfolio-', '');
          const matchingMember = familyMembers.find(m => m.id === memberId);
          if (matchingMember) {
            return { ...p, capital: matchingMember.amount };
          }
          return p;
        } else {
          // Strategic portfolio - use total investment
          return { ...p, capital: totalInvestment };
        }
      });
      await saveData({
        portfolios: portfoliosToSave,
        scenarios: allScenarios,
        familyMembers: familyMembers,
        default_scenario_id: activeScenario.name
      });
    } catch (error) {
      console.error('Error saving data:', error);
    }
  }, [portfolios, selectedScenario, customScenario, scenariosState, isLoading, totalInvestment, familyMembers]);

  // Debounced auto-save
  useEffect(() => {
    if (isLoading) return;
    const timer = setTimeout(() => {
      saveToBackend();
    }, 1000); // Save 1 second after last change
    return () => clearTimeout(timer);
  }, [portfolios, selectedScenario, customScenario, saveToBackend, isLoading]);

  // Update member portfolios when family members change (but not during initial load)
  useEffect(() => {
    // Don't run during initial load - let loadInitialData handle portfolio creation
    if (isLoading) return;
    
    setPortfolios(prev => {
      // If no portfolios exist yet, don't do anything (wait for load)
      // Also check if we have strategic portfolios - if not, we're still loading
      const hasStrategicPortfolios = prev.some(p => !p.name.endsWith("'s Portfolio"));
      if (prev.length === 0 || !hasStrategicPortfolios) return prev;
      
      // Keep strategic portfolios, update their capital to total investment
      const strategic = prev.filter(p => !p.name.endsWith("'s Portfolio"));
      const updatedStrategic = strategic.map(p => ({ ...p, capital: totalInvestment }));
      
      // Sort family members by display_order to maintain order
      const sortedFamilyMembers = [...familyMembers].sort((a, b) => (a.displayOrder || 0) - (b.displayOrder || 0));
      
        // Create/update member portfolios - sync with family members in display_order
        const memberPortfolios = sortedFamilyMembers.map(member => {
          // Find existing portfolio by member ID (most reliable)
          const existing = prev.find(p => p.id === `member-portfolio-${member.id}`);
          
          // Create/update portfolio with current member data
          const updatedPortfolio = createMemberPortfolio(member, existing);
          
          // Preserve allocation and rules from existing portfolio if it exists
          // But always use member's color if set
          if (existing) {
            updatedPortfolio.allocation = existing.allocation;
            updatedPortfolio.rules = existing.rules;
          }
          // Update color from member if member has a color set
          if (member.color) {
            updatedPortfolio.color = member.color;
          }
          
          return updatedPortfolio;
        });
      
      return [...updatedStrategic, ...memberPortfolios];
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [familyMembers, totalInvestment, isLoading]);

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

  // Create evolution data map for easy lookup
  const evolutionDataMap = useMemo(() => {
    const map: { [portfolioId: string]: YearResult[] } = {};
    simulationResults.forEach(result => {
      map[result.portfolioId] = result.years;
    });
    return map;
  }, [simulationResults]);

  // Calculate total portfolio width to match all components
  const totalPortfolioWidth = useMemo(() => {
    const regularCardWidth = 320;
    const familyCardWidth = 160;
    const gap = 24; // gap-6 = 1.5rem = 24px
    
    const numPortfolios = portfolios.length;
    if (numPortfolios === 0) return 'fit-content';
    
    // Check if we have 2+ member portfolios (which means we'll show the family total card)
    const memberPortfolios = portfolios.filter(p => p.name.endsWith("'s Portfolio"));
    const shouldShowFamilyCard = memberPortfolios.length > 1;
    const numCards = shouldShowFamilyCard ? numPortfolios + 1 : numPortfolios; // +1 for family card
    
    // Calculate width: regular cards + family card (if present)
    let totalWidth = numPortfolios * regularCardWidth;
    if (shouldShowFamilyCard) {
      totalWidth += familyCardWidth; // Add the narrow family card
    }
    
    // Add gaps between all cards
    totalWidth += (numCards - 1) * gap;
    
    return `${totalWidth}px`;
  }, [portfolios]);

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
      <Header width={totalPortfolioWidth} />
      
      <div className="mx-auto px-4 py-6" style={{ width: totalPortfolioWidth, maxWidth: '95vw' }}>
        {/* Family Members & Investment Amount */}
        <div className="mb-6" style={{ width: totalPortfolioWidth }}>
          <FamilyMembersManager
            familyMembers={familyMembers}
            onUpdate={setFamilyMembers}
          />
        </div>

        {/* Scenario Selector */}
        <div className="mb-6" style={{ width: totalPortfolioWidth }}>
          <ScenarioSelector
            scenarios={scenariosState}
            selectedScenario={safeScenario}
            onSelect={handleScenarioSelect}
            onUpdate={handleScenarioUpdate}
            onSave={handleScenarioSave}
          />
        </div>

        {/* Portfolios - Strategic portfolios and member portfolios */}
        <div className="flex flex-nowrap gap-6 mb-6 items-stretch" style={{ width: 'fit-content' }}>
          {(() => {
            // Separate strategic and member portfolios
            const strategicPortfolios = portfolios.filter(p => !p.name.endsWith("'s Portfolio"));
            const memberPortfolios = portfolios.filter(p => p.name.endsWith("'s Portfolio"));
            
            // Sort strategic by template order
            const sortedStrategic = strategicPortfolios.sort((a, b) => {
              const aIndex = strategicTemplates.findIndex(t => t.name === a.name);
              const bIndex = strategicTemplates.findIndex(t => t.name === b.name);
              return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
            });
            
            // Sort member portfolios by family member display_order
            const sortedMembers = memberPortfolios.sort((a, b) => {
              const aMemberId = a.id.replace('member-portfolio-', '');
              const bMemberId = b.id.replace('member-portfolio-', '');
              const aMember = familyMembers.find(m => m.id === aMemberId);
              const bMember = familyMembers.find(m => m.id === bMemberId);
              const aOrder = aMember?.displayOrder ?? 999;
              const bOrder = bMember?.displayOrder ?? 999;
              return aOrder - bOrder;
            });
            
            const regularCardWidth = 320;
            const familyCardWidth = 160;
            
            return (
              <>
                {/* Strategic Portfolios */}
                {sortedStrategic.map(portfolio => {
                  const evolutionData = evolutionDataMap[portfolio.id];
                  return (
                    <div key={portfolio.id} className="flex flex-shrink-0" style={{ width: `${regularCardWidth}px` }}>
                      <PortfolioCard
                        portfolio={portfolio}
                        onUpdate={handleUpdatePortfolio}
                        evolutionData={evolutionData}
                        showReal={showReal}
                      />
                    </div>
                  );
                })}
                
                {/* Family Total Card - only show if there are 2+ member portfolios */}
                {sortedMembers.length > 1 && (
                  <div className="flex flex-shrink-0" style={{ width: `${familyCardWidth}px` }}>
                    <FamilyTotalCard
                      memberPortfolios={sortedMembers}
                      evolutionData={evolutionDataMap}
                      showReal={showReal}
                    />
                  </div>
                )}
                
                {/* Member Portfolios */}
                {sortedMembers.map(portfolio => {
                  const evolutionData = evolutionDataMap[portfolio.id];
                  return (
                    <div key={portfolio.id} className="flex flex-shrink-0" style={{ width: `${regularCardWidth}px` }}>
                      <PortfolioCard
                        portfolio={portfolio}
                        onUpdate={handleUpdatePortfolio}
                        evolutionData={evolutionData}
                        showReal={showReal}
                      />
                    </div>
                  );
                })}
              </>
            );
          })()}
        </div>

        {/* Charts Section */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6" style={{ width: totalPortfolioWidth }}>
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
      </div>
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<ProtectedRoute requireAuth={false}><Login /></ProtectedRoute>} />
      <Route path="/register" element={<ProtectedRoute requireAuth={false}><Register /></ProtectedRoute>} />
      <Route path="/admin" element={<AdminRoute><AdminPanel /></AdminRoute>} />
      <Route path="/" element={<ProtectedRoute><PortfolioApp /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
