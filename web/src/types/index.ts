// Core account types

export interface Account {
  code: string;
  name: string;
  type: string;
  canonType: string;
  reportCode?: string;
  taxCode?: string;
  description?: string;
}

export interface MappedAccount extends Account {
  predictedCode: string;
  mappingName: string;
  source: string;
  needsReview: boolean;
  hasActivity: boolean;
  closingBalance: number;
  correctedName?: string;
  overrideCode?: string;
  overrideReason?: string;
}

// Rule engine

export interface Rule {
  name: string;
  code: string;
  priority: number;
  keywords: string[];
  keywordsAll: string[];
  keywordsExclude: string[];
  rawTypes: string[];
  canonTypes: string[];
  typeExclude: string[];
  template?: string;
  ownerContext?: boolean;
  nameOnly?: boolean;
  industries?: string[];
  notes?: string;
}

export interface MatchContext {
  normalisedText: string;
  normalisedName: string;
  rawType: string;
  canonType: string;
  templateName: string;
  ownerKeywords: string[];
  industry: string;
}

export interface RulesData {
  version: number;
  updatedAt: string;
  dictionaries: Record<string, string[]>;
  rules: Rule[];
}

// Chart Check Report

export interface GLEntry {
  accountCode: string;
  accountName: string;
  openingBalance: number;
  debit: number;
  credit: number;
  netMovement: number;
  closingBalance: number;
  accountType: string;
}

export interface DepAsset {
  costAccount: string;
  name: string;
  assetNumber: string;
  assetType: string;
  expenseAccount: string;
  accumDepAccount: string;
  cost: number;
  closingAccumDep: number;
  closingValue: number;
}

export interface EntityParams {
  displayName: string;
  legalName: string;
  abn: string;
  directors: string[];
  trustees: string[];
  signatories: string[];
}

export interface BeneficiaryEntry {
  accountCode: string;
  accountName: string;
  beneficiaryName: string;
}

export interface ChartCheckData {
  glSummary: GLEntry[];
  depSchedule: DepAsset[];
  clientParams: EntityParams;
  beneficiaryAccounts: BeneficiaryEntry[];
}

// Group Relationships

export interface GroupEntity {
  uuid: string;
  name: string;
  businessStructure: string;
}

export interface Relationship {
  entityUuid: string;
  entityName: string;
  type: string;
  relatedClient: string;
  current: boolean;
  shares?: number;
  percentage?: number;
}

export interface GroupRelationships {
  groupName: string;
  entities: GroupEntity[];
  relationships: Relationship[];
}

// System reference data

export interface SystemMapping {
  reportingCode: string;
  name: string;
  isLeaf: boolean;
}

export interface TemplateEntry {
  code: string;
  reportingCode: string;
  name: string;
  type: string;
  reportingName: string;
}

// App

export type TemplateName =
  | 'Company'
  | 'Trust'
  | 'Partnership'
  | 'SoleTrader'
  | 'XeroHandi';
