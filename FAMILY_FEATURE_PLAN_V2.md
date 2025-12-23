# Family Feature Implementation Plan V2 - Per-Member Portfolios

## Overview
Each family member has their own portfolio with their own allocation. This simplifies the model and makes it more intuitive - each member manages their own portfolio independently.

## Design Decisions

### 1. **Per-Member Portfolio Approach**
- **Decision**: Each family member gets their own portfolio
- **Rationale**: 
  - Simpler and more intuitive - one portfolio per member
  - Each member's portfolio is independent
  - Each portfolio has its own capital (member's contribution amount)
  - Each portfolio has its own allocation percentages
  - Can still calculate combined totals for display/comparison
  - Removes complexity of memberAllocations field

### 2. **Portfolio Structure**
- **Strategic Portfolios** (Aggressive Growth, Balanced Allocation, Income Focused): Reference/guidance only
- **Member Portfolios**: One portfolio per family member
  - Portfolio name: "{Member Name}'s Portfolio" (e.g., "Nicolae's Portfolio")
  - Portfolio capital: Member's contribution amount
  - Portfolio allocation: Member's allocation percentages
  - Portfolio color: Assigned based on member order

### 3. **Combined View**
- Can calculate combined allocation across all member portfolios
- Combined capital = sum of all member portfolios
- Combined allocation = weighted average of all member allocations
- Display combined totals for comparison with strategic portfolios

## Implementation Changes

### Backend Changes
- Remove `member_allocations` field from PortfolioModel (no longer needed)
- Each family member's portfolio is stored as a separate Portfolio record
- Portfolio name pattern: "{memberName}'s Portfolio"

### Frontend Changes
- Remove MemberAllocationInput component (no longer needed)
- Remove memberAllocations from Portfolio interface
- Create member portfolios dynamically when family members are added
- Update PortfolioCard to work with standard allocations (no special case)
- Add combined view/calculation for displaying totals

### UI Changes
- Member portfolios displayed alongside strategic portfolios
- Each member portfolio is a standard portfolio card
- Can show combined totals in a summary view
- Remove special 2-column layout (all portfolios same width)

## Migration Strategy
- When loading existing data:
  - If "Current Allocation" portfolio exists with memberAllocations, split it into per-member portfolios
  - Create one portfolio per family member
  - Use member's name in portfolio name
  - Set portfolio capital to member's amount
  - Use member's allocation from memberAllocations

