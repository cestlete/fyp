from openie import StanfordOpenIE
import streamlit as st
# HOGS is a heuristic algorithm that presumes that edges with greater arity
import csv
import os

import HOGS
import networkx as nx
import random

global mode
global term_separator
global max_topology_distance
global semantic_threshold
global max_relational_distance
global numeric_offset

properties = {
    'openie.affinity_probability_cap': 2 / 3,
}

max_relational_distance = 0.99
semantic_threshold = 0.9  # MAXimum semantic distance allowed.
max_topology_distance = 500  # in terms of a node's in/out degree
numeric_offset = 1000
mode = "English"
# mode = 'Code'
if mode == "English":
    term_separator = "_"  # Map2Graphs.term_separator
else:
    term_separator = ":"

epsilon = 100
current_best_mapping = []
bestEverMapping = []


def generate_2_homomorphic_graphs(graph_size=55, prob=0.10, deletions=0):
    """ Generate 2 graphs, 1st with fewer edges than the second, forming Target and Source graphs. """
    global numeric_offset
    G1, G2 = nx.MultiDiGraph(), nx.MultiDiGraph()
    G1 = nx.erdos_renyi_graph(graph_size, prob, directed=True)
    # G1 = nx.scale_free_graph(graph_size, prob) #, 0.5, prob, directed=True)
    # G1.add_edges_from( [(0, 1), (1, 0), (1,0), (1, 2), (2, 3)] ) random_k_out_graph, newman_watts_strogatz_graph , ...
    if G1.number_of_edges() > 3000:  # Largest Graph Considered
        print("Graph might be too big, Return [] [] ")
        return nx.MultiDiGraph(), nx.MultiDiGraph(), [], []
    tripl_list1, tripli_list2, list1_paired_edges = [], [], []
    remapping = {}
    for a, b in G1.edges():
        tripl_list1.append([a, "to", b])
    remapping.clear()
    for node in G1.nodes():
        remapping[node] = node + numeric_offset
    G2 = nx.relabel_nodes(G1, remapping, copy=True)
    for a, b in G2.edges():
        tripli_list2.append([a, "to", b])
    for i in range(deletions):
        if len(tripl_list1) > 0:
            indx = random.randint(0, len(tripl_list1) - 1)
            a, b = tripl_list1[indx][0], tripl_list1[indx][2]
            del (tripl_list1[indx])
            G1.remove_edge(a, b)  # delete edges
    return G1, G2, tripl_list1, tripli_list2


# ##########################################################################################################
# ############################################## MCS #######################################################
# ##########################################################################################################


def returnEdgesAsList(G, remove_none_rels=True):  # returnEdgesAsList(sourceGraph)
    """ returns a list of lists, each composed of triples"""
    res = []
    for (u, v, reln) in G.edges.data('label'):
        res.append([u, reln, v])
    return res


# returnEdgesAsList(targetGraph)


def return_best_ismags_mapping_BACKUP(largest_common_subgraphs, t_encoding, t_decoding, G2):
    best_node_score, best_edge_score, best_node_map, best_pred_map = 0, 0, [], []
    for dic in largest_common_subgraphs:  # dict of alternative solutions
        dict_1 = list(dic.items())
        dict_1.sort(key=lambda i: i[0])
        node_map, pred_map = [], []  # node_map - mapped_edges, pred_map - list_of_mapped_preds_2
        for z in t_decoding.keys():
            node_map.append((z, t_decoding[z]))
        for n1, n2 in G2.edges():
            if n1 in t_encoding.keys() and n2 in t_encoding.keys():
                pred_map.append([(t_encoding[n1], t_encoding[n2]), (n1, n2)])
        pred_map.sort(key=lambda i: i[0])

        nod_scor, edg_scor = score_numeric_mapping(pred_map)
        if edg_scor > best_edge_score:
            best_edge_score = edg_scor
            best_pred_map = pred_map
            best_node_map = node_map
            best_node_score = nod_scor
    return best_edge_score, best_node_map, best_pred_map


def return_best_ismags_mapping(largest_common_subgraphs, t_encoding, s_decoding, G1, G2):
    best_pred_map, best_edge_score, best_node_map, node_map, iter_n = [], 0, [], {}, 0
    largest_pred_map_size, best_edge_score, largest_node_map, largest_map_iter, best_score_iter = 0, 0, [], 0, 0
    largest_pred_map = []
    for this_mapping in largest_common_subgraphs:  # dict of alternative solutions
        pred_map = []  # node_map - mapped_edges, pred_map - list_of_mapped_preds_2
        node_map.clear()
        for n1, n2 in G2.edges():
            tn1_enc = t_encoding[n1]
            tn2_enc = t_encoding[n2]
            if tn1_enc in this_mapping.keys() and tn2_enc in this_mapping.keys():
                tn1_map, tn2_map = this_mapping[tn1_enc], this_mapping[tn2_enc]
                if tn1_map in s_decoding.keys() and tn2_map in s_decoding.keys():
                    tn1_map_decod, tn2_map_decod = s_decoding[tn1_map], s_decoding[tn2_map]
                    if (tn1_map_decod, tn2_map_decod) in G1.edges():
                        pred_map.append([(tn1_map_decod, tn2_map_decod), (n1, n2)])
                        node_map[tn1_map_decod] = n1
                        node_map[tn2_map_decod] = n2
        nod_scor, edg_scor = score_numeric_mapping(pred_map)
        if edg_scor > best_edge_score:  # Best Scoring (CORRECT)
            best_edge_score = edg_scor
            best_pred_map = pred_map
            best_node_map.clear()
            best_node_map = node_map
            best_score_iter = iter_n
        if len(pred_map) > largest_pred_map_size:  # Best size
            largest_pred_map_size = len(pred_map)
            largest_node_map = len(node_map)
            largest_pred_map = pred_map
            largest_map_iter = iter_n
    boleyn = best_score_iter == largest_map_iter and best_score_iter > 0
    return best_edge_score, best_node_map, best_pred_map, largest_pred_map, largest_node_map, boleyn  # largest_node_map


def score_numeric_mapping(pred_list):
    from sematch.semantic.similarity import WordNetSimilarity
    wns = WordNetSimilarity()

    # """ Evaluation of mapped predicates """
    global numeric_offset
    mapped_nodes, mismapped_nodes = set(), set()
    num_mapped_preds = 0
    if not pred_list:
        return 0, 0

    def node_match(node1, node2):
        if isinstance(node1, str) and isinstance(node2, str):
            return node1 == node2
        elif isinstance(node1, int) and isinstance(node2, int):
            return node1 == node2 - numeric_offset
        return False

    if len(pred_list[0]) == 3:  # includes edge label
        for a, b, _ in pred_list:
            similarity0 = wns.word_similarity(a[0], b[0], 'li')
            if similarity0 >= 0.1:
                mapped_nodes.add(a[0])
            else:
                mismapped_nodes.add(a[0])
            similarity2 = wns.word_similarity(a[2], b[2], 'li')
            if similarity2 >= 0.1:
                mapped_nodes.add(a[2])
            else:
                mismapped_nodes.add(a[2])
            if similarity0 >= 0.1 and similarity2 >= 0.1:
                num_mapped_preds += 1

    return len(mapped_nodes), num_mapped_preds


def generate_counterpart_graph(mapped_preds, G1, G2):
    # print("mapped_preds:", mapped_preds)
    counterpart_grf = nx.MultiDiGraph()
    G1_unmapped = G1.copy()
    G2_unmapped = G2.copy()
    for a, b, scr in mapped_preds:  # tgt, src, score
        counterpart_grf.add_edge(str(a[0]) + " - " + str(b[0]), str(a[2]) + " - " + str(b[2]),
                                 label=str(a[1]) + " - " + str(b[1]))
        # Remove edge from G1_unmapped
        if a[1] is None:
            G1_unmapped.remove_edge(a[0], a[2])
        else:
            edges_to_remove = [(u, v, key) for u, v, key, data in G1_unmapped.edges(keys=True, data=True) if
                               u == a[0] and v == a[2] and data.get('label') == a[1]]
            for u, v, key in edges_to_remove:
                G1_unmapped.remove_edge(u, v, key=key)

        # Remove edge from G2_unmapped
        if b[1] is None:
            G2_unmapped.remove_edge(b[0], b[2])
        else:
            edges_to_remove = [(u, v, key) for u, v, key, data in G2_unmapped.edges(keys=True, data=True) if
                               u == b[0] and v == b[2] and data.get('label') == b[1]]
            for u, v, key in edges_to_remove:
                G2_unmapped.remove_edge(u, v, key=key)

    G1_unmapped.remove_nodes_from(list(nx.isolates(G1_unmapped)))  # remove unattached nodes
    G2_unmapped.remove_nodes_from(list(nx.isolates(G2_unmapped)))
    return counterpart_grf, G1_unmapped, G2_unmapped


def generate_ismags_counterpart_graph(mapped_preds, G1, G2):
    """ Accepts lists of paired edges - without accompanying score"""
    counterpart_grf = nx.MultiDiGraph()
    G1_unmapped = G1.copy()
    G2_unmapped = G2.copy()
    for a, b in mapped_preds:  # 2 values, not 3
        counterpart_grf.add_edge(str(a[0]) + " " + str(b[0]),
                                 str(a[1]) + " " + str(b[1]))  # , label = str(a[1])+"-"+str(b[1]))
        if G1_unmapped.has_edge(a[0], a[1]):
            G1_unmapped.remove_edge(a[0], a[1])
        # else:
        #    G1_unmapped.remove_edge(a[0], a[2]) #, label = a[1])
        if b[1] == None:
            G2_unmapped.remove_edge(b[0], b[1])
        else:
            G2_unmapped.remove_edge(b[0], b[1])  # , label = a[1])
    G1_unmapped.remove_nodes_from(list(nx.isolates(G1_unmapped)))
    G2_unmapped.remove_nodes_from(list(nx.isolates(G2_unmapped)))
    return counterpart_grf, G1_unmapped, G2_unmapped


def encode_graph_labels(grf):
    nu_grf = nx.Graph()  # nx.OrderedGraph()
    s_encoding = {}  # label, number
    s_decoding = {}  # number, label
    label = 0
    for x, y in grf.edges():
        if not x in s_encoding.keys():
            s_decoding[label] = x
            s_encoding[x] = label
            label += 1
        if not y in s_encoding.keys():
            s_decoding[label] = y
            s_encoding[y] = label
            label += 1
        nu_grf.add_edge(s_encoding[x], s_encoding[y])
    return nu_grf, s_encoding, s_decoding


def analyse_lists_of_paired_tuples(tup_list_1, tup_list_2):  # 2 lists of edges defining 2 graphs
    """ comon, l1_only, l2_only = analyse_lists_of_paired_tuples(list1_paired_edges, pred_map_2) """
    common = [[(a, b), (c, d)] for [(a, b), (c, d)] in tup_list_1 for [(p, q), (r, s)] in tup_list_2 if
              ((a == p) and (b == q) and (c == r) and (d == s))]
    list_1_only = tup_list_1.copy()
    list_2_only = tup_list_2.copy()
    list_1_only = [list_1_only.remove([(a, b), (c, d)]) for [(a, b), (c, d)] in common for [(p, q), (r, s)] in
                   tup_list_1 if ((a == p) and (b == q) and (c == r) and (d == s))]
    list_2_only = [list_2_only.remove([(a, b), (c, d)]) for [(a, b), (c, d)] in common for [(p, q), (r, s)] in
                   tup_list_2 if ((a == p) and (b == q) and (c == r) and (d == s))]
    return common, list_1_only, list_2_only


# ########################################################################################################
# ########################################################################################################
# ########################################################################################################
def read_oie_file(file_path):
    triples = []
    with open(file_path, 'r', encoding='utf8') as file:
        reader = csv.reader(file)
        next(reader, None)  # 跳过第一行
        for row in reader:
            if len(row) == 3:
                triples.append(row)
            else:
                print(f"Skipping invalid row: {row}")  # Debug: invalid row
    return triples


# def generate_graphs_from_oie_files(file1, file2):
#     triples1 = read_oie_file(file1)
#     triples2 = read_oie_file(file2)
#
#     G1 = generate_graph_from_triples(triples1)
#     G2 = generate_graph_from_triples(triples2)
#
#     return G1, G2, triples1, triples2

def graph_isomorphism_experiment(G1, G2, graph_size=20, prob=0.10, deletions=0):
    import time
    import ShowGraphs

    # G1, G2 = nx.MultiDiGraph(), nx.MultiDiGraph()
    list1_paired_edges = []

    G1.graph['Graphid'] = str(graph_size) + " " + str(prob) + " " + str(deletions) + " orig"
    G2.graph['Graphid'] = str(graph_size) + " " + str(prob) + " " + str(deletions) + " vrnt"
    # print("# Edges ", G1.number_of_edges(), "&", G2.number_of_edges(), end=" ")
    max_map_nodes = min(G1.number_of_nodes() - nx.number_of_isolates(G1),
                        G2.number_of_nodes() - nx.number_of_isolates(G2))
    max_map_edges = max(min(G1.number_of_edges(), G2.number_of_edges()), 0.987)  # avoid /0 error
    G1_preds = returnEdgesAsList(G1)
    G2_preds = returnEdgesAsList(G2)
    ################################## HOGS algorithm ###########################################
    time1 = time.time()
    grf_id = int((time1 * 10000000) % 1000)
    show_FDG = False
    if show_FDG:
        ShowGraphs.show_blended_space(G1_preds, [], [], \
                                      "Expt " + str(G1.number_of_nodes()) + " " + str(G1.number_of_edges()) + " " + str(
                                          grf_id) + " Tgt")
        ShowGraphs.show_blended_space(G2_preds, [], [], \
                                      "Expt " + str(G1.number_of_nodes()) + " " + str(G1.number_of_edges()) + " " + str(
                                          grf_id) + " Src")
    list_of_mapped_preds_1, number_mapped_predicates, mapping = HOGS.generate_and_explore_mapping_space(G1, G2, False)
    time2 = time.time() - time1
    list_of_mapped_concepts = list(mapping)  # return_list_of_mapped_concepts(list_of_mapped_preds_1)
    counterpart_grf, G1_unmapped, G2_unmapped = generate_counterpart_graph(list_of_mapped_preds_1, G1, G2)
    largest_cc = {}
    if counterpart_grf.number_of_nodes() > 0:
        largest_cc = max(nx.weakly_connected_components(counterpart_grf), key=len)
    for pred1, pred2, val in list_of_mapped_preds_1:
        a, _, c = pred1
        x, _, z = pred2
        list1_paired_edges.append([(a, c), (x, z)])
    list1_paired_edges.sort(key=lambda i: i[0])
    scr_nodes, scr_edges = score_numeric_mapping(
        list_of_mapped_preds_1)  # DUPLICATION, see return_list_of_mapped_concepts()
    generic_preds = returnEdgesAsList(counterpart_grf)
    unmapped_G1_edges = returnEdgesAsList(G1_unmapped)
    unmapped_G2_edges = returnEdgesAsList(G2_unmapped)
    scr = 100 * scr_edges / max_map_edges
    if show_FDG:
        ShowGraphs.show_blended_space_big_nodes(G1, generic_preds, unmapped_G1_edges, unmapped_G2_edges, \
                                                "Expt " + str(G1.number_of_nodes()) + " " + str(
                                                    G1.number_of_edges()) + " " + str(grf_id) + " HOGS")
    # print("HOGS # Edges ,", G1.number_of_edges(), ", ", G2.number_of_edges(), ", Prob,", prob,
    #     " ,  T=,", round(time2, 2), ", Del=,", deletions, " , SIZE:  Map'd Nods=,",
    #       len(list_of_mapped_concepts),",/,", max_map_nodes, " , Edg=,", len(list_of_mapped_preds_1), ",/,", max_map_edges, ", ",
    #       round(len(list_of_mapped_preds_1)/max_map_edges*100,2), ",%    CORRECT: Prft-Edg ,", round(scr, 2),
    #       ",%    Prft-Nod,", scr_nodes, " , Pred-Scor ,", scr_edges, ",  LCC,", len(largest_cc), " ,  ID,", grf_id)
    similarity = round(len(list_of_mapped_preds_1) / max_map_edges * 100, 2)
    # print("Similarity: ", Similarity, "% ")
    return similarity
    # ############################################# VF++ #############################################
    time1 = time.time()
    dic_res = nx.vf2pp_isomorphism(G1, G2)
    time_diff = time.time() - time1
    # if dic_res:
    #    print("VF2pp isomorphism detected", time_diff, end=" ")
    # ############################################# ISMAGS #############################################
    new_G1_ismags, s_encoding, s_decoding = encode_graph_labels(G1)
    new_G2_ismags, t_encoding, t_decoding = encode_graph_labels(G2)
    # largest_common_subgraph = nx.MultiDiGraph()
    counterpart_grf.clear()
    ismags = nx.isomorphism.ISMAGS(new_G1_ismags, new_G2_ismags)
    time1 = time.time()
    largest_common_subgraph = list(ismags.largest_common_subgraph(symmetry=False))
    time2 = time.time()
    scr_2, node_map_2, pred_map_2, largest_pred_map, largest_node_map, same_iter \
        = return_best_ismags_mapping(largest_common_subgraph, t_encoding, s_decoding, G1, G2)
    scr_nodes, scr_edges = score_numeric_mapping(pred_map_2)
    if scr_edges > 0:
        counterpart_grf, G1_unmapped, G2_unmapped = generate_ismags_counterpart_graph(pred_map_2, G1, G2)
    elif len(largest_pred_map) > 0:  # for incorrect mappings
        counterpart_grf, G1_unmapped, G2_unmapped = generate_ismags_counterpart_graph(largest_pred_map, G1, G2)
    if counterpart_grf.number_of_edges() > 0:
        largest_cc = max(nx.weakly_connected_components(counterpart_grf), key=len)
    print("# Edges ", G1.number_of_edges(), ", ", G2.number_of_edges(), " Prob", prob,
          "  ISMAGS  T=", round(time2 - time1, 2), "  DEL=", deletions, "  SIZE:   Map'D Nods=",
          largest_node_map, "/", max_map_nodes, "  Edg=", len(largest_pred_map), "/", max_map_edges, " ",
          round(len(largest_pred_map) / max_map_edges * 100, 2), "%   CORRECT: Pref-Edg ",
          round(100 * scr_edges / max_map_edges, 2),
          "%   Prft-Nod", scr_nodes, "  Pred-Scor ", scr_edges, "  LCC", len(largest_cc), "   ID", grf_id)
    generic_preds = returnEdgesAsList(counterpart_grf)
    unmapped_G1_edges = returnEdgesAsList(G1_unmapped)
    unmapped_G2_edges = returnEdgesAsList(G2_unmapped)
    if show_FDG:
        ShowGraphs.show_blended_space(generic_preds, unmapped_G1_edges, unmapped_G2_edges,
                                      "Expt " + str(G1.number_of_nodes()) + " " + str(G1.number_of_edges()) + " " + str(
                                          grf_id) + " ISMAGS")
    print()
    # stop()


def run_graph_matching_tests(G1, G2):
    for num_of_nodes in range(20, 50, 10):  # nodes
        tot_edg_scr, loop_count = 0, 0
        print("\n#######", num_of_nodes, "#########################################")
        for prob in range(50, 101, 50):
            prob1 = prob / 1000
            for dels in [0, 1]:  # in range(0, 10, 5):
                # print("EXPT.    Deletions=", dels, end="  ")
                for repetition_n in range(3):  # reproducibility
                    graph_isomorphism_experiment(G1, G2, graph_size=num_of_nodes, prob=prob1, deletions=dels)
                    loop_count += 1
                    print()
                print("")
                # stop()
    # print("\n\nOVERALL", tot_edg_scr/loop_count)
    # stop()


def process_document(txt):
    with StanfordOpenIE(properties=properties) as client:
        triples = client.annotate(txt)
        return [[triple['subject'], triple['relation'], triple['object']] for triple in triples]


def run_single_graph_matching_test(G1, G2):
    # select the parameters for the graph
    num_of_nodes = 30  # select a middle number of nodes
    prob = 0.075  # select a middle probability
    dels = 0  # don't delete any edges

    # execute the single graph matching test
    similarity = graph_isomorphism_experiment(G1, G2, graph_size=num_of_nodes, prob=prob, deletions=dels)

    print()
    return similarity


def generate_graph_from_triple(triples):
    G = nx.MultiDiGraph()
    for subject, relation, obj in triples:
        G.add_edge(subject, obj, label=relation)
    return G


def generate_graphs_from_oie_file(file1):
    triples1 = read_oie_file(file1)
    G1 = generate_graph_from_triple(triples1)
    return G1


####################################Streamlit####################################
st.title("Find the most similar Aesop's Fable")

text1 = st.text_area("Enter your text:", "")

if st.button("Analyze"):
    if text1:
        text1 = text1.strip()
        triples1 = process_document(text1)
        G1 = generate_graph_from_triple(triples1)

        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Build the relative path to the data directory
        data_dir = os.path.join(current_dir, '..', 'data')

        # Specify the directory containing the OIE files
        oie_directory = os.path.join(data_dir, 'Aesops-OIE')

        # Specify the directory containing the text files
        txt_directory = os.path.join(data_dir, 'Aesops')

        max_similarity = 0
        most_similar_file = ""

        # all the files in the OIE directory
        for filename in os.listdir(oie_directory):
            if filename.endswith(".OIE"):
                file_path = os.path.join(oie_directory, filename)

                G2 = generate_graphs_from_oie_file(file_path)

                # calculate the similarity between the two graphs
                similarity = run_single_graph_matching_test(G1, G2)
                print(similarity)

                # update the most similar file, only if the similarity is greater than the current max_similarity
                if similarity is not None and similarity > max_similarity:
                    max_similarity = similarity
                    most_similar_file = os.path.splitext(filename)[0]

        if most_similar_file:
            st.write("Analysis Results:")
            st.write(f"The most similar Aesop's Fable is: {most_similar_file}")
            st.write(f"Similarity: {max_similarity}%")

            # read the content of the most similar fable
            txt_file_path = os.path.join(txt_directory, f"{most_similar_file}.txt")
            if os.path.exists(txt_file_path):
                with open(txt_file_path, 'r', encoding='utf-8') as file:
                    file_content = file.read()
                st.write("Content of the most similar fable:")
                with st.expander("Click to view the fable", expanded=True):
                    st.markdown(file_content)
            else:
                st.warning(f"The corresponding text file ({most_similar_file}.txt) was not found.")

            st.success("Analysis complete.")
        else:
            st.warning("No valid similarity scores were found.")
    else:
        st.warning("Please enter the text.")
