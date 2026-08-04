=== FunctionDef ===
(program (function_definition name:(word) @name) @__anchor__)

=== Assignment ===
(program (variable_assignment name:(variable_name) @name value:(_) @value) @__anchor__)

=== Heredoc ===
(program (redirected_statement (heredoc_redirect descriptor:(file_descriptor)? @descriptor (heredoc_start) @start (heredoc_body) @body (heredoc_end)? @end) @__anchor__))
