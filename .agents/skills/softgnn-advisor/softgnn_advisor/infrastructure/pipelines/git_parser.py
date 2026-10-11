from git import Repo
from git.exc import InvalidGitRepositoryError
import os
import networkx as nx
from softgnn_advisor.core.file_filters import is_relevant_file, normalize_repo_path
from softgnn_advisor.core.developer_aliases import resolve_developer_identity

class CodebaseGitParser:
    def __init__(self, root_dir, developer_aliases=None):
        self.root_dir = root_dir
        self.developer_aliases = developer_aliases or {}
        try:
            self.repo = Repo(root_dir)
        except (InvalidGitRepositoryError, Exception):
            self.repo = None
            print(f"[Warning] No Git repository found at {root_dir}. SoftGNN will operate without Git history (Graceful Degradation).")
        self.graph = nx.MultiDiGraph()
        self.developer_nodes = set()
        self.commit_nodes = set()
        self.edges = []
        
    def parse_all(self, max_commits=500):
        print(f"Scanning Git History: {self.root_dir}")
        if self.repo is None:
            return self.graph

        commits = list(self.repo.iter_commits('HEAD', max_count=max_commits))
        file_nodes = set()  # track file IDs seen from git

        for commit in commits:
            commit_id = f"COMMIT:{commit.hexsha}"
            author_email = commit.author.email
            author_name = resolve_developer_identity(commit.author.name, author_email, self.developer_aliases)
            dev_id = f"DEV:{author_email}"

            self.commit_nodes.add(commit_id)
            self.developer_nodes.add((dev_id, author_name))

            # Relation: Developer authored Commit
            self.edges.append((dev_id, 'authored_by', commit_id))

            # Find which files were modified
            if not commit.parents:
                continue

            parent = commit.parents[0]
            try:
                diffs = parent.diff(commit)
            except Exception:
                continue

            for diff in diffs:
                path = diff.b_path or diff.a_path
                if not path:
                    continue

                # Normalize to forward slashes (matches AST parser on Windows)
                norm_path = normalize_repo_path(path)
                if not is_relevant_file(norm_path, allow_docs=True):
                    continue

                file_id = f"FILE:{norm_path}"
                file_nodes.add((file_id, norm_path))

                # Relation: Commit modifies File
                self.edges.append((commit_id, 'modifies', file_id))

        # Explicitly add file nodes with type='File' so they merge correctly
        # with AST file nodes (which share the same FILE:... ID format).
        for file_id, norm_path in file_nodes:
            fname = norm_path.split('/')[-1]
            self.graph.add_node(file_id, type='File', name=fname)

        return self._build_graph()

    def _build_graph(self):
        for dev_id, name in self.developer_nodes:
            self.graph.add_node(dev_id, type='Developer', name=name)
        for commit_id in self.commit_nodes:
            self.graph.add_node(commit_id, type='Commit', name=commit_id.split(':')[1][:7])
            
        for src, rel, dst in self.edges:
            self.graph.add_edge(src, dst, type=rel)
            
        print(f"Extracted {self.graph.number_of_nodes()} git nodes and {self.graph.number_of_edges()} git edges.")
        return self.graph

if __name__ == '__main__':
    parser = CodebaseGitParser(".")
    G = parser.parse_all()
    print("Git Graph built successfully!")

