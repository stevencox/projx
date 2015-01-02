from itertools import cycle, islice
from pyparsing import (Word, alphanums, OneOrMore, ZeroOrMore, Group, 
                       stringEnd, Suppress, Literal, CaselessKeyword,
                       Optional, Forward, quotedString, Dict, nestedExpr)


# Used throughout as a variable/attr name.
var = Word(alphanums, "_" + alphanums)
dot_op = Suppress(Literal("."))


################ VERBS AND DIRECT OBJECTS ###################
# ProjX verbs.
verb = (
    CaselessKeyword("MATCH") |
    CaselessKeyword("TRANSFER") |
    CaselessKeyword("PROJECT") |
    CaselessKeyword("COMBINE") |
    CaselessKeyword("RETURN")
)
verb.setParseAction(lambda t: t[0].lower())

# Objects of verbs.
obj = (
    CaselessKeyword("ATTRS") |
    CaselessKeyword("EDGES") |
    CaselessKeyword("GRAPH") |
    CaselessKeyword("SUBGRAPH") |
    CaselessKeyword("TABLE")
)
obj.setParseAction(lambda t: t[0].lower())


################ NODE AND EDGE PATTERNS ###################
# Used for node and edge patterns.
seperator = Suppress(Literal(":"))
tp = seperator + Word(alphanums, "_" + alphanums)

# Node type pattern.
node_open = Suppress(Literal("("))
node_close = Suppress(Literal(")"))
node_content = Group(
    var.setResultsName("alias") +
    Optional(tp).setResultsName("type")
)


node = node_open + node_content + node_close

# Edge patterns.
edge_marker = Suppress(Literal("-"))
edge_open = Suppress(Literal("["))
edge_close = Suppress(Literal("]"))
edge_content = edge_open + Group(
    var.setResultsName("alias") +
    Optional(tp).setResultsName("type")
) + edge_close

edge = edge_marker + Optional(edge_content + edge_marker)

# Recursive pattern match.
pattern = Forward() 
pattern << node.setResultsName("nodes", listAllMatches=True) + ZeroOrMore(
    edge.setResultsName("edges", listAllMatches=True) + pattern
)


################### PREDICATE CLAUSES #######################
# Predicates
pred = (
    CaselessKeyword("DELETE") |
    CaselessKeyword("METHOD") |
    CaselessKeyword("WHERE") |
    CaselessKeyword("SET")
)
pred.setParseAction(lambda t: t[0].lower())

# Used for the creation of new nodes with combine or project.
new = Literal("NEW")
new.setParseAction(lambda t: t[0].lower())

# Right part of getter setter.
right = (
    var.setResultsName("type2") + dot_op + var.setResultsName("attr2") |
    quotedString.setResultsName("attr2")
)

left = new | var 
# This can be used with both SET and WHERE. 
gettr_settr = Group(
    left.setResultsName("type1") +
    dot_op +
    var.setResultsName("attr1") +
    Literal("=") +
    right
)

# Recursive definition for multiple predicate objects.
attr = gettr_settr | var
pred_obj = Forward()
pred_obj << attr.setResultsName("pred_objects", listAllMatches=True) + ZeroOrMore(
    Suppress(Literal(",")) + pred_obj
)
 
# Allow multiple predicate clauses.
pred_clause = ZeroOrMore(
    Group(
        pred.setResultsName("predicate") +
        pred_obj
    ).setResultsName("pred_clauses", listAllMatches=True)
).setResultsName("predicates", listAllMatches=True)


###################### QUERY ###########################
# Valid query clause.
clause = Group(
    verb.setResultsName("verb") + 
    Optional(obj).setResultsName("object") +
    pattern.setResultsName("pattern") +
    pred_clause
)

parser = OneOrMore(clause) + stringEnd

def parse_query(query):
    """
    REWRITE - Not gonna use big parser, just a routine with small parse elements.
    """
    clauses = parser.parseString(query)
    match = clauses[0]
    obj = match.get("object", "subgraph")
    pattern = match["pattern"]
    nodes = [
        {"node": {"alias": node[0]["alias"], "type": node[0].get("type", [""])[0]}} 
        for node in pattern["nodes"]
    ]
    edges = [
        {"edge": {"alias": edge[0].get("alias", ""), "type": edge[0].get("type", [""])[0]}} 
        for edge in pattern["edges"]
    ]
    traversal = roundrobin(nodes, edges)
    transformers = []
    import ipdb; ipdb.set_trace()
    for clause in clauses[1:]:
        verb = clause["verb"]
        
        # Method not implemented yet, will have to change grammar to include over
        obj = clause.get("object", "")
        pattern = clause["pattern"]
        pred_clause = clause.get("predicates", "")
        if pred_clause:
            to_set = []
            delete = []
            # Method is weird
            method = ''
            preds = pred_clause[0]['pred_clauses']
            for pred in preds:
                p = pred["predicate"]
                if p == 'set':
                    to_set = pred['pred_objects']
                    for attr in to_set.asList():

                elif p == 'delete':
                    delete = pred['pred_objects'].asList()
        #    elif p == 'method':
        #        method = pred['pred_objects'][0]
        transformer = {
            verb: {
                "method": {obj: {}} 
            }
        }
        transformers.append(transformer)
    etl = {
        "extractor": {
            "networkx": {
                "class": obj,
                "traversal": list(traversal)
            }
        },
        "tansformers": transformers,
        "loader": {
            "networkx": {}
        }
    }
    return traversal 


def roundrobin(*iterables):
    "roundrobin('ABC', 'D', 'EF') --> A D E B F C"
    # Recipe credited to George Sakkis
    pending = len(iterables)
    nexts = cycle(iter(it).next for it in iterables)
    while pending:
        try:
            for next in nexts:
                yield next()
        except StopIteration:
            pending -= 1
            nexts = cycle(islice(nexts, pending))
