import os
from pathlib import Path


class UniversalCoverageMapper:
    """Universal runtime coverage parser supporting standard LCOV (lcov.info) and Go coverprofile formats."""

    @staticmethod
    def parse_lcov(lcov_path_or_content: str) -> dict:
        """Parse LCOV format into {normalized_file_path: {line_no: hit_count}}."""
        if os.path.exists(lcov_path_or_content):
            content = Path(lcov_path_or_content).read_text(encoding='utf-8', errors='replace')
        else:
            content = lcov_path_or_content

        coverage_by_file = {}
        current_file = None

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith('SF:'):
                raw_path = line[3:].strip()
                current_file = raw_path.replace('\\', '/')
                coverage_by_file.setdefault(current_file, {})
            elif line.startswith('DA:') and current_file:
                parts = line[3:].split(',')
                if len(parts) >= 2:
                    try:
                        lineno = int(parts[0])
                        count = int(parts[1])
                        coverage_by_file[current_file][lineno] = count
                    except ValueError:
                        pass
            elif line == 'end_of_record':
                current_file = None

        return coverage_by_file

    @staticmethod
    def parse_go_coverprofile(profile_path_or_content: str) -> dict:
        """Parse Go coverage profile (coverage.out) into {normalized_file_path: {line_no: hit_count}}."""
        if os.path.exists(profile_path_or_content):
            content = Path(profile_path_or_content).read_text(encoding='utf-8', errors='replace')
        else:
            content = profile_path_or_content

        coverage_by_file = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('mode:'):
                continue

            # format: path/file.go:startline.col,endline.col statements count
            parts = line.split()
            if len(parts) >= 3:
                block = parts[0]
                try:
                    count = int(parts[2])
                except ValueError:
                    count = 0

                if ':' in block:
                    filepath, range_part = block.rsplit(':', 1)
                    filepath = filepath.replace('\\', '/')
                    coverage_by_file.setdefault(filepath, {})
                    if ',' in range_part:
                        start_part, end_part = range_part.split(',')
                        try:
                            start_line = int(start_part.split('.')[0])
                            end_line = int(end_part.split('.')[0])
                            for l in range(start_line, end_line + 1):
                                coverage_by_file[filepath][l] = coverage_by_file[filepath].get(l, 0) + count
                        except ValueError:
                            pass

        return coverage_by_file

    @classmethod
    def load_coverage(cls, path_or_content: str) -> dict:
        """Auto-detect coverage format (LCOV vs Go coverprofile) and parse."""
        sample = path_or_content[:500] if len(path_or_content) > 500 else path_or_content
        if os.path.exists(path_or_content):
            try:
                sample = Path(path_or_content).read_text(encoding='utf-8', errors='replace')[:500]
            except Exception:
                pass

        if 'mode:' in sample or '.go:' in sample:
            return cls.parse_go_coverprofile(path_or_content)
        return cls.parse_lcov(path_or_content)

    @classmethod
    def verify_proof(
        cls,
        target_id: str,
        function_ranges: dict,
        coverage_data: dict,
        source_file: str = None,
    ) -> dict:
        """Verify whether target_id was executed in coverage_data."""
        # 1. Locate function range for target_id
        target_range = None
        matched_file = None

        norm_source_file = source_file.replace('\\', '/').strip('/') if source_file else None

        for file_path, fns in function_ranges.items():
            norm_file = file_path.replace('\\', '/').strip('/')
            if norm_source_file and not (norm_file.endswith(norm_source_file) or norm_source_file.endswith(norm_file)):
                continue
            for fn in fns:
                if fn.get('function_id') == target_id or fn.get('name') == target_id.replace('FUNC:', ''):
                    target_range = fn
                    matched_file = file_path
                    break
            if target_range:
                break

        if not target_range:
            return {
                'status': 'error',
                'proof_status': 'fail',
                'target_id': target_id,
                'message': f"Target '{target_id}' was not found in the parsed function ranges.",
                'covered_fraction': 0.0,
                'covered_lines': [],
                'covered_line_count': 0,
                'function_line_count': 0,
            }

        start_line = target_range['start']
        end_line = target_range['end']
        fn_line_count = max(1, end_line - start_line + 1)

        # 2. Find file in coverage_data
        cov_lines = {}
        for cov_file, lines_map in coverage_data.items():
            norm_cov = cov_file.replace('\\', '/').strip('/')
            norm_match = matched_file.replace('\\', '/').strip('/')
            if norm_cov.endswith(norm_match) or norm_match.endswith(norm_cov):
                cov_lines = lines_map
                break

        # 3. Compute executed lines
        executed = sorted([
            l for l in range(start_line, end_line + 1)
            if cov_lines.get(l, 0) > 0
        ])
        covered_count = len(executed)
        fraction = round(covered_count / fn_line_count, 4)

        if covered_count > 0:
            msg = (
                f"Universal Runtime Proof CONFIRMED: {target_id} "
                f"({fraction:.0%} coverage, {covered_count}/{fn_line_count} lines executed)."
            )
            return {
                'status': 'success',
                'proof_status': 'pass',
                'target_id': target_id,
                'source_file': matched_file,
                'message': msg,
                'covered_fraction': fraction,
                'covered_lines': executed,
                'covered_line_count': covered_count,
                'function_line_count': fn_line_count,
            }
        else:
            msg = (
                f"Universal Runtime Proof FAILED: 0 lines of {target_id} "
                f"(lines {start_line}-{end_line} in {matched_file}) were executed in the coverage report. "
                "Ensure the test calls the function and does not mock out its body."
            )
            return {
                'status': 'success',
                'proof_status': 'fail',
                'target_id': target_id,
                'source_file': matched_file,
                'message': msg,
                'covered_fraction': 0.0,
                'covered_lines': [],
                'covered_line_count': 0,
                'function_line_count': fn_line_count,
            }
