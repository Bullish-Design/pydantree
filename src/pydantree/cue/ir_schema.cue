package pydantree

#Capture: {
    name: string
    node?: string
    source?: {
        file: string
        line?: >=1 & int
        column?: >=1 & int
    }
}

#Pattern: {
    id?: string
    pattern: string
    captures: [...#Capture]
}

#QueryMetadata: {
    language: string
    query_type: string
    source_scm: string
    generated_by?: string
}

#IR: {
    version: "v1"
    patterns: [...#Pattern]
    query_metadata: #QueryMetadata
}
