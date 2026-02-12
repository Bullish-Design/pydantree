package pydantree

#Manifest: {
    pipeline_version: string
    input_hashes: [string]: string
    toolchain_versions: [string]: string
    output_file_hashes: [string]: string
    ingest_fingerprint: string
    normalize_fingerprint: string
    emit_fingerprint: string
    query_count: int
    module_count: int
    generated_at: string
}
