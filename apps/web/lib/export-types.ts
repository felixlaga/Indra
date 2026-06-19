export interface ExportDescriptor {
  format: string;
  label: string;
  filename: string;
  media_type: string;
  description: string;
  preserves_validation_status: boolean;
}

export interface ExportCatalog {
  session_id: string;
  artifacts: ExportDescriptor[];
}
