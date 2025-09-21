export interface Document {
  id: string;
  filename: string;
  s3_key: string;
  size: number;
  upload_date: string;
  categories: string[];
  processed?: boolean;
  bedrock_processed?: boolean;
  extraction_confidence?: number;
  medical_fields_extracted?: number;
  key_findings?: string[];
}

export interface DocumentFilters {
  categories: string[];
  dateFrom?: string;
  dateTo?: string;
  sizeMin?: number;
  sizeMax?: number;
  processed?: boolean;
  search?: string;
  confidenceMin?: number;
  confidenceMax?: number;
}

export interface DocumentsResponse {
  documents: Document[];
  total: number;
}

export interface Category {
  value: string;
  label: string;
}