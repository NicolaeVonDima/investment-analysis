# Family Feature Implementation Plan

## Overview
Add support for multiple family members contributing to the investment pool, where each member has a name and contribution amount. The total investment amount will be the sum of all family member contributions.

## Design Decisions

### 1. **Hybrid Portfolio Approach**
- **Decision**: 
  - **Strategic Portfolios** (Aggressive Growth, Balanced Allocation, Income Focused): **Reference/guidance only** - shared allocations for comparison purposes
  - **Current Allocation Portfolio**: **Active portfolio** - per-member allocations to optimize broker plans
- **Rationale**: 
  - Strategic portfolios serve as guidance/reference for target allocations
  - They don't use family member breakdowns - they're conceptual allocations
  - Current Allocation is the actual working portfolio that needs per-member breakdown
  - Each family member may have different broker accounts with different fee structures
  - Allows splitting investments across accounts to minimize total commissions
  - Current Allocation needs more UI space to display per-member inputs

### 2. **Family Member Data Structure**
- Each family member has:
  - `id`: Unique identifier (UUID or auto-increment)
  - `name`: Display name (e.g., "Nicolae", "Liana", "Daughter")
  - `amount`: Contribution amount in EUR
  - `order`: Display order (for consistent UI ordering)
  - `created_at`, `updated_at`: Timestamps

### 2.1 **Per-Member Allocations (Current Allocation Portfolio Only)**
- For "Current Allocation" portfolio, each family member has their own allocation percentages:
  - `memberAllocations`: Map of `memberId` → `{ vwce, tvbetetf, ernx, ayeg, fidelis }`
  - Each member's allocations are percentages (0-100) that sum to 100% per member
  - **Total portfolio allocation** = weighted sum of all member allocations
  - Example:
    - Nicolae: 60% of total, allocates 50% VWCE, 30% TVBETETF, 20% ERNX
    - Liana: 40% of total, allocates 40% VWCE, 35% TVBETETF, 25% ERNX
    - **Combined**: (60% * 50% + 40% * 40%) = 46% VWCE total

### 3. **Total Investment Calculation**
- `globalInvestment = sum(familyMembers.map(m => m.amount))`
- Strategic portfolios use `globalInvestment` as their capital (existing behavior)
- Current Allocation portfolio uses `globalInvestment` as total capital
- When a family member's amount changes, recalculate total and update all portfolios

### 3.1 **Current Allocation Portfolio Calculation**
- Each member's capital = `(member.amount / totalInvestment) * globalInvestment`
- Each member's allocation percentages apply to their portion
- Total allocation per asset = weighted average:
  ```
  totalVWCE = sum(member.weight * member.allocation.vwce) for all members
  where member.weight = member.amount / totalInvestment
  ```
- This allows optimizing broker plans: split investments across accounts to minimize fees

## Implementation Phases

### Phase 1: Data Model & Backend (Foundation)

#### 1.1 Backend Database Model
**File**: `backend/app/models.py`
- Create `FamilyMemberModel` table:
  ```python
  class FamilyMemberModel(Base):
      __tablename__ = "family_members"
      
      id = Column(String, primary_key=True, index=True)  # UUID
      name = Column(String, nullable=False)
      amount = Column(Float, nullable=False)
      display_order = Column(Integer, nullable=False, default=0)
      created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
      updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
  ```

- Update `PortfolioModel` to support per-member allocations:
  ```python
  # Add new field (optional, only for "Current Allocation" portfolio)
  member_allocations = Column(JSON, nullable=True)  
  # Format: { "member-id-1": { "vwce": 50, "tvbetetf": 30, ... }, "member-id-2": {...} }
  # If null, use standard shared allocation
  ```

#### 1.2 Backend Schema
**File**: `backend/app/schemas.py`
- Add `FamilyMemberBase`, `FamilyMemberCreate`, `FamilyMemberResponse`
- Update `SaveDataRequest` to include `familyMembers: list[FamilyMemberBase]`
- Update `LoadDataResponse` to include `familyMembers: list[FamilyMemberResponse]`

#### 1.3 Backend API Endpoints
**File**: `backend/app/main.py`
- Update `/api/data/save` to handle family members
- Update `/api/data/load` to return family members
- Add migration logic to create default family member from existing `globalInvestment` if no members exist

#### 1.4 Database Migration
**File**: `backend/app/database.py`
- Add `ALTER TABLE` migration for `family_members` table
- Handle existing data: if no family members exist, create one default member with name "Primary" and amount = sum of all portfolio capitals

### Phase 2: Frontend Types & State Management

#### 2.1 TypeScript Types
**File**: `src/types/index.ts`
- Add `FamilyMember` interface:
  ```typescript
  export interface FamilyMember {
    id: string;
    name: string;
    amount: number;
    displayOrder?: number;
  }
  ```

- Update `Portfolio` interface to support per-member allocations:
  ```typescript
  export interface Portfolio {
    // ... existing fields ...
    allocation: {
      vwce: number;
      tvbetetf: number;
      ernx: number;
      ayeg: number;
      fidelis: number;
    };
    // NEW: Per-member allocations (only for "Current Allocation" portfolio)
    memberAllocations?: {
      [memberId: string]: {
        vwce: number;
        tvbetetf: number;
        ernx: number;
        ayeg: number;
        fidelis: number;
      };
    };
    // ... rest of fields ...
  }
  ```

#### 2.2 State Management
**File**: `src/App.tsx`
- Replace `globalInvestment` state with `familyMembers: FamilyMember[]`
- Add computed `totalInvestment` derived from sum of family member amounts
- Update all references to `globalInvestment` to use `totalInvestment`
- Add functions:
  - `addFamilyMember(name: string, amount: number)`
  - `updateFamilyMember(id: string, updates: Partial<FamilyMember>)`
  - `removeFamilyMember(id: string)`
  - `reorderFamilyMembers(members: FamilyMember[])`

#### 2.2.1 Current Allocation Portfolio Logic
**File**: `src/App.tsx` and `src/utils/simulation.ts`
- When portfolio is "Current Allocation" and has `memberAllocations`:
  1. Calculate weighted total allocation per asset
  2. Use this total allocation for simulation
  3. Store both member allocations and calculated total
- When member amounts change, recalculate weighted allocations
- When member allocations change, recalculate total allocation

### Phase 3: UI Components

#### 3.1 Family Members Manager Component
**New File**: `src/components/FamilyMembersManager.tsx`
- Display list of family members with:
  - Name input field (editable)
  - Amount input field (editable, formatted as currency)
  - Delete button (disabled if only one member)
  - Add member button
- Show total investment amount prominently
- Show per-member percentage of total
- Auto-save on changes (debounced)
- Validation:
  - At least one member required
  - Names must be non-empty
  - Amounts must be >= 0
  - Total must be > 0

#### 3.1.1 Per-Member Allocation Component (Current Allocation Only)
**New File**: `src/components/PortfolioBuilder/MemberAllocationInput.tsx`
- Display per-member allocation inputs for "Current Allocation" portfolio
- **Layout**: Optimized for wider card (2-column span)
- For each family member, show:
  - Member name and contribution amount (with percentage of total)
  - Allocation sliders/inputs for each asset (VWCE, TVBETETF, ERNX, AYEG, FIDELIS)
  - Each member's section in a compact, scannable format
  - Validation: each member's allocations must sum to 100%
- Show calculated total allocation per asset (weighted sum) prominently
- Visual indicator showing how totals are calculated
- **Grid layout**: Consider 2-column layout within the component for better space usage
  - Left column: Member inputs
  - Right column: Total allocation summary
- Purpose: Optimize broker plans by splitting investments across accounts

#### 3.2 Update Header/Investment Section
**File**: `src/App.tsx` (Investment Amount section)
- Replace single investment input with `<FamilyMembersManager />`
- Show breakdown: "Total: €X (Nicolae: €Y, Liana: €Z)"
- Keep existing portfolio update logic (strategic portfolios use total)

#### 3.2.1 Update PortfolioCard for Current Allocation
**File**: `src/components/PortfolioBuilder/PortfolioCard.tsx`
- Detect if portfolio is "Current Allocation"
- If yes, show `<MemberAllocationInput />` instead of standard allocation sliders
- Calculate and display total allocation from member allocations
- Show per-member breakdown in allocation summary
- Keep standard allocation sliders for other portfolios (reference only)

#### 3.2.2 Layout Adjustments for Current Allocation
**File**: `src/App.tsx` (Portfolio grid layout)
- Current portfolio grid: `grid-cols-1 md:grid-cols-2 lg:grid-cols-4`
- **New layout**: Make Current Allocation wider
  - Option A: `grid-cols-1 md:grid-cols-2 lg:grid-cols-5` where Current Allocation spans 2 columns
  - Option B: Separate Current Allocation into its own row with full width
  - Option C: `grid-cols-1 md:grid-cols-3 lg:grid-cols-4` where Current Allocation spans 2 columns on large screens
- **Recommended**: Option C - Current Allocation takes 2 columns, others take 1 column each
  - Layout: `[Aggressive] [Balanced] [Income] [Current (2 cols)]`
  - On smaller screens, stack normally
- Update PortfolioCard to accept `colSpan` prop for Current Allocation

#### 3.3 API Service Updates
**File**: `src/services/api.ts`
- Update `saveData()` to include family members
- Update `loadData()` to return family members
- Add transformation functions for family member data

### Phase 4: Data Migration & Backward Compatibility

#### 4.1 Migration Strategy
- **On Load**: If no family members exist in database but portfolios have capital:
  1. Sum all portfolio capitals (they should be equal, but handle edge case)
  2. Create default family member: `{ id: 'default-1', name: 'Primary', amount: sum }`
  3. Save to database on next save

- **On Save**: Always save family members array (even if single member)

#### 4.2 Backward Compatibility
- Existing data without family members should work seamlessly
- Migration happens automatically on first load after update
- No data loss - existing portfolio capitals preserved

### Phase 5: Calculation & Simulation Updates

#### 5.1 Allocation Calculation Logic
**File**: `src/utils/allocationCalculator.ts` (new utility)
- Function to calculate total allocation from member allocations:
  ```typescript
  function calculateTotalAllocation(
    memberAllocations: { [memberId: string]: Allocation },
    familyMembers: FamilyMember[]
  ): Allocation {
    // Weighted sum: total = sum(member.weight * member.allocation)
    // where weight = member.amount / totalInvestment
  }
  ```

#### 5.2 Simulation Updates
**File**: `src/utils/simulation.ts`
- Before simulation, check if portfolio has `memberAllocations`
- If yes, calculate total allocation and use it for simulation
- Simulation logic remains unchanged (uses total allocation)

#### 5.3 Portfolio Update Logic
**File**: `src/components/PortfolioBuilder/PortfolioCard.tsx`
- When updating "Current Allocation" portfolio:
  - If updating member allocations, recalculate total allocation
  - If updating total allocation directly, distribute proportionally (optional)
  - Always keep member allocations and total in sync

### Phase 6: Enhanced Features (Future Considerations)

#### 6.1 Broker Commission Optimization (Future)
- Add broker fee structures per member
- Calculate optimal split to minimize total commissions
- Suggest allocation adjustments based on fee structures

#### 6.2 Member-Specific Scenarios (Optional Future)
- Different risk profiles per member
- Age-based scenarios (e.g., daughter's longer time horizon)

#### 6.3 Contribution Tracking (Optional Future)
- Track contribution history
- Show contribution percentages
- Visualize contribution timeline

## File Changes Summary

### New Files
1. `src/components/FamilyMembersManager.tsx` - Main UI component for managing family members
2. `src/components/PortfolioBuilder/MemberAllocationInput.tsx` - Per-member allocation inputs for Current Allocation portfolio
3. `src/utils/allocationCalculator.ts` - Utility to calculate total allocation from member allocations

### Modified Files

#### Backend
1. `backend/app/models.py` - Add FamilyMemberModel
2. `backend/app/schemas.py` - Add family member schemas
3. `backend/app/main.py` - Update save/load endpoints
4. `backend/app/database.py` - Add migration for family_members table

#### Frontend
1. `src/types/index.ts` - Add FamilyMember interface, update Portfolio interface
2. `src/App.tsx` - Replace globalInvestment with familyMembers state, handle Current Allocation logic, update grid layout
3. `src/services/api.ts` - Add family member save/load logic, handle memberAllocations
4. `src/components/PortfolioBuilder/PortfolioCard.tsx` - Add per-member allocation UI for Current Allocation, support colSpan prop
5. `src/utils/simulation.ts` - Handle memberAllocations in simulation
6. `src/components/Header.tsx` - (Optional) Update header text if needed

## Testing Checklist

### Family Members
- [ ] Add family member
- [ ] Edit family member name
- [ ] Edit family member amount
- [ ] Delete family member (when multiple exist)
- [ ] Prevent deleting last member
- [ ] Total investment updates correctly
- [ ] Portfolios update when total changes
- [ ] Save/load family members to/from database
- [ ] Migration from old single-investment format
- [ ] Validation (empty names, negative amounts)
- [ ] UI responsive and accessible

### Current Allocation Portfolio
- [ ] Per-member allocation inputs appear only for "Current Allocation"
- [ ] Current Allocation card is wider (2 columns) than other portfolio cards
- [ ] Layout responsive: wider on large screens, normal on mobile
- [ ] Each member's allocations sum to 100%
- [ ] Total allocation calculated correctly (weighted sum)
- [ ] Total allocation updates when member amounts change
- [ ] Total allocation updates when member allocations change
- [ ] Simulation uses calculated total allocation
- [ ] Save/load memberAllocations to/from database
- [ ] Migration: existing Current Allocation portfolio gets default member allocations
- [ ] Other portfolios (Aggressive, Balanced, Income) use standard shared allocation and standard width
- [ ] Other portfolios are clearly marked as "reference/guidance only"
- [ ] Validation: prevent invalid allocations (negative, >100%, etc.)
- [ ] UI is scannable and not cramped despite more inputs

## Implementation Order

1. **Phase 1** (Backend): Database, models, schemas, API endpoints
2. **Phase 2** (Frontend Core): Types, state management, API integration
3. **Phase 3** (UI): FamilyMembersManager component, integration into App
4. **Phase 4** (Migration): Backward compatibility and data migration
5. **Phase 5** (Current Allocation): Per-member allocation calculation and UI
6. **Phase 6** (Polish): Validation, error handling, edge cases, testing

## Notes

### General
- Family members are additive - total = sum of all amounts
- UI should be intuitive: add/edit/remove members easily
- Consider using UUIDs for family member IDs to avoid conflicts
- Display order allows users to customize the order (e.g., parents first, then children)

### Portfolio Roles
- **Strategic Portfolios** (Aggressive Growth, Balanced Allocation, Income Focused):
  - **Role**: Reference/guidance portfolios
  - **Purpose**: Show different allocation strategies for comparison
  - **Family Members**: NOT applicable - these are conceptual
  - **UI**: Standard width (1 column), standard allocation sliders
  - **User Action**: Compare these strategies to inform decisions
  
- **Current Allocation Portfolio**:
  - **Role**: Active working portfolio
  - **Purpose**: Actual allocation to implement, optimized for broker commissions
  - **Family Members**: REQUIRED - each member has their own allocations
  - **UI**: Wider layout (2 columns) to accommodate per-member inputs
  - **User Action**: Configure per-member allocations to optimize broker plans

### Portfolio Behavior
- **Strategic Portfolios** (Aggressive Growth, Balanced Allocation, Income Focused):
  - **Purpose**: Reference/guidance only - show target allocation strategies
  - **Behavior**: Use shared allocation (existing behavior)
  - **Family Members**: NOT used - these are conceptual portfolios for comparison
  - **Capital**: Uses total investment for display/simulation purposes only
  - **UI**: Standard width, standard allocation sliders
  
- **Current Allocation Portfolio**:
  - **Purpose**: Active working portfolio - actual allocation to implement
  - **Behavior**: Uses per-member allocations to optimize broker plans
  - **Family Members**: REQUIRED - each member has their own allocation percentages
  - **Capital**: Uses total investment, but allocations are per-member
  - **Total allocation**: Weighted sum of member allocations
  - **UI**: Wider layout (2 columns) to accommodate per-member inputs
  - **Use case**: Split investments across different broker accounts to minimize commissions
  - Example: Nicolae's broker has lower fees for VWCE, so allocate more VWCE to his account

### Calculation Example
If you have:
- Nicolae: €120,000 (60% of total), allocates 50% VWCE, 30% TVBETETF, 20% ERNX
- Liana: €80,000 (40% of total), allocates 40% VWCE, 35% TVBETETF, 25% ERNX

Total allocation:
- VWCE: (60% × 50%) + (40% × 40%) = 30% + 16% = 46%
- TVBETETF: (60% × 30%) + (40% × 35%) = 18% + 14% = 32%
- ERNX: (60% × 20%) + (40% × 25%) = 12% + 10% = 22%

This allows optimizing broker commissions by strategically allocating assets across accounts.

