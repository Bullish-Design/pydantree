(source_file (section) @record)

-- inner --

(section (entry key:(identifier) @key value:(identifier) @host (#eq? @key "host"))) @__anchor__

(section (entry key:(identifier) @key value:(string (string_content) @host) (#eq? @key "host"))) @__anchor__

(section (entry key:(identifier) @key value:(integer) @port (#eq? @key "port"))) @__anchor__

(section (entry key:(identifier) @key value:(boolean) @debug (#eq? @key "debug"))) @__anchor__

(section (entry key:(identifier) @key value:(identifier) @title (#eq? @key "title"))) @__anchor__

(section (entry key:(identifier) @key value:(string (string_content) @title) (#eq? @key "title"))) @__anchor__