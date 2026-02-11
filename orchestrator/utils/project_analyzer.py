"""프로젝트 사전 분석기.

타겟 프로젝트를 Python 코드로 분석하여 프로필을 생성한다.
AI를 사용하지 않으므로 비용 0, 시간 1-2초.

2단계 분석:
  1. 정적 프로필 (프로젝트 전체, 캐시) → .project-profile.json
  2. 동적 타겟 컨텍스트 (기획서별, 매번 생성) → 프롬프트에 삽입할 문자열
"""

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ProjectAnalyzer:
    """타겟 프로젝트를 분석하고 프로필을 관리한다."""

    PROFILE_FILENAME = '.project-profile.json'

    # 모듈 내부 구조 스캔 시 핵심 파일 패턴
    KEY_FILE_PATTERNS = [
        '*Entity.java', '*Repository.java', '*Facade.java',
        '*Controller.java', '*Service.java', '*UseCase.java',
        '*Usecase.java', '*Config.java', '*Filter.java',
        '*Provider.java', '*Client.java',
    ]

    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.profile_path = self.project_path / self.PROFILE_FILENAME

    # ── 공개 API ──────────────────────────────────────────

    def get_or_create_profile(self) -> Dict[str, Any]:
        """프로필이 있으면 로드, 없거나 stale이면 생성/갱신한다.

        Returns:
            프로젝트 프로필 딕셔너리
        """
        current_commit = self._get_current_commit()
        existing = self._load_profile()

        if existing and existing.get('analyzed_commit') == current_commit:
            logger.info("프로젝트 프로필 캐시 사용 (commit 동일)")
            return existing

        if existing:
            logger.info(
                f"프로젝트 변경 감지: "
                f"{existing.get('analyzed_commit', '?')[:8]} → "
                f"{current_commit[:8]}, 증분 갱신"
            )
            profile = self._update_incremental(existing, current_commit)
        else:
            logger.info("프로젝트 프로필 최초 생성")
            profile = self._analyze_full(current_commit)

        self._save_profile(profile)
        return profile

    def generate_target_context(
        self,
        profile: Dict[str, Any],
        spec_content: str,
        max_file_lines: int = 50
    ) -> str:
        """기획서 기반으로 관련 모듈의 핵심 코드를 추출한다.

        Args:
            profile: 프로젝트 프로필
            spec_content: 기획서 원문
            max_file_lines: 파일당 최대 읽기 라인 수

        Returns:
            프롬프트에 삽입할 컨텍스트 문자열
        """
        relevant_modules = self._find_relevant_modules(profile, spec_content)
        sections = []

        # 프로젝트 개요
        sections.append(self._format_overview(profile))

        # 모듈 구조 테이블
        sections.append(self._format_module_table(profile))

        # 관련 모듈의 핵심 코드
        if relevant_modules:
            sections.append(
                self._format_relevant_code(
                    profile, relevant_modules, max_file_lines
                )
            )

        return '\n\n'.join(sections)

    # ── 정적 분석 (1단계) ─────────────────────────────────

    def _analyze_full(self, commit: str) -> Dict[str, Any]:
        """프로젝트 전체를 분석하여 프로필을 생성한다."""
        profile: Dict[str, Any] = {
            'analyzed_commit': commit,
            'project_name': self.project_path.name,
        }

        # 프로젝트 타입 감지
        project_type = self._detect_project_type()
        profile['project_type'] = project_type

        # 빌드 시스템별 분석
        if project_type.get('build_system') == 'gradle':
            profile.update(self._analyze_gradle())
        elif project_type.get('build_system') == 'maven':
            profile.update(self._analyze_maven())
        elif project_type.get('build_system') == 'npm':
            profile.update(self._analyze_npm())
        else:
            profile.update(self._analyze_generic())

        # 모듈별 상세 분석
        modules = profile.get('modules', {})
        for mod_name, mod_info in modules.items():
            mod_path = self.project_path / mod_info.get('path', mod_name)
            if mod_path.is_dir():
                mod_info.update(self._analyze_module(mod_path, mod_name))

        # 아키텍처 패턴 감지
        profile['architecture_pattern'] = self._detect_architecture_pattern(
            modules
        )

        # 패키지 컨벤션 감지
        profile['package_convention'] = self._detect_package_convention()

        return profile

    def _update_incremental(
        self, existing: Dict[str, Any], new_commit: str
    ) -> Dict[str, Any]:
        """변경된 파일만 분석하여 프로필을 갱신한다."""
        old_commit = existing.get('analyzed_commit', '')
        changed_files = self._get_changed_files(old_commit, new_commit)

        if not changed_files:
            existing['analyzed_commit'] = new_commit
            return existing

        # 변경된 모듈 식별
        changed_modules = set()
        for f in changed_files:
            parts = Path(f).parts
            if parts:
                changed_modules.add(parts[0])

        logger.info(
            f"변경된 모듈: {changed_modules} "
            f"({len(changed_files)}개 파일)"
        )

        # 변경된 모듈만 재분석
        modules = existing.get('modules', {})
        for mod_name in changed_modules:
            if mod_name in modules:
                mod_path = self.project_path / modules[mod_name].get(
                    'path', mod_name
                )
                if mod_path.is_dir():
                    modules[mod_name].update(
                        self._analyze_module(mod_path, mod_name)
                    )

        # 빌드 파일이 변경되었으면 전체 재분석
        build_files_changed = any(
            f in changed_files
            for f in [
                'build.gradle', 'settings.gradle',
                'pom.xml', 'package.json'
            ]
        )
        if build_files_changed:
            logger.info("빌드 파일 변경 감지, 프로젝트 타입 재분석")
            existing['project_type'] = self._detect_project_type()

        existing['analyzed_commit'] = new_commit
        return existing

    # ── 프로젝트 타입 감지 ────────────────────────────────

    def _detect_project_type(self) -> Dict[str, str]:
        """프로젝트 타입과 빌드 시스템을 감지한다."""
        result: Dict[str, str] = {
            'language': 'unknown',
            'framework': 'unknown',
            'build_system': 'unknown',
        }

        # Gradle (Java/Kotlin)
        if (self.project_path / 'build.gradle').exists() or \
           (self.project_path / 'build.gradle.kts').exists():
            result['build_system'] = 'gradle'
            result['language'] = 'java'

            build_content = self._read_file_safe('build.gradle')
            if not build_content:
                build_content = self._read_file_safe('build.gradle.kts')

            if build_content:
                if 'kotlin' in build_content.lower():
                    result['language'] = 'kotlin'
                if 'spring' in build_content.lower():
                    result['framework'] = 'spring-boot'
                    # 버전 추출
                    ver = re.search(
                        r"spring.boot.*version\s*['\"](\d+\.\d+\.\d+)",
                        build_content
                    )
                    if ver:
                        result['framework_version'] = ver.group(1)

            # Java 버전 추출
            java_ver = re.search(
                r'languageVersion.*of\((\d+)\)', build_content or ''
            )
            if java_ver:
                result['java_version'] = java_ver.group(1)

        # Maven
        elif (self.project_path / 'pom.xml').exists():
            result['build_system'] = 'maven'
            result['language'] = 'java'
            pom = self._read_file_safe('pom.xml')
            if pom and 'spring-boot' in pom:
                result['framework'] = 'spring-boot'

        # Node.js
        elif (self.project_path / 'package.json').exists():
            result['build_system'] = 'npm'
            result['language'] = 'javascript'
            pkg = self._read_file_safe('package.json')
            if pkg:
                try:
                    pkg_data = json.loads(pkg)
                    deps = {
                        **pkg_data.get('dependencies', {}),
                        **pkg_data.get('devDependencies', {})
                    }
                    if 'react' in deps:
                        result['framework'] = 'react'
                    elif 'next' in deps:
                        result['framework'] = 'nextjs'
                    elif 'express' in deps:
                        result['framework'] = 'express'
                    if 'typescript' in deps:
                        result['language'] = 'typescript'
                except json.JSONDecodeError:
                    pass

        # Python
        elif (self.project_path / 'pyproject.toml').exists() or \
             (self.project_path / 'setup.py').exists():
            result['build_system'] = 'pip'
            result['language'] = 'python'

        return result

    # ── Gradle 분석 ───────────────────────────────────────

    def _analyze_gradle(self) -> Dict[str, Any]:
        """Gradle 프로젝트를 분석한다."""
        result: Dict[str, Any] = {'modules': {}}

        # settings.gradle에서 모듈 목록 추출
        settings = self._read_file_safe('settings.gradle')
        if not settings:
            settings = self._read_file_safe('settings.gradle.kts')

        if settings:
            module_names = re.findall(
                r"include\s+['\"]([^'\"]+)['\"]", settings
            )
            for name in module_names:
                result['modules'][name] = {
                    'path': name,
                    'key_classes': [],
                    'role': '',
                }

        return result

    def _analyze_maven(self) -> Dict[str, Any]:
        """Maven 프로젝트를 분석한다."""
        result: Dict[str, Any] = {'modules': {}}
        pom = self._read_file_safe('pom.xml')
        if pom:
            modules = re.findall(r'<module>([^<]+)</module>', pom)
            for name in modules:
                result['modules'][name] = {
                    'path': name,
                    'key_classes': [],
                    'role': '',
                }
        return result

    def _analyze_npm(self) -> Dict[str, Any]:
        """npm 프로젝트를 분석한다."""
        result: Dict[str, Any] = {'modules': {}}
        pkg = self._read_file_safe('package.json')
        if pkg:
            try:
                pkg_data = json.loads(pkg)
                # 주요 의존성 기록
                result['dependencies'] = list(
                    pkg_data.get('dependencies', {}).keys()
                )[:20]
                # workspaces가 있으면 모듈
                workspaces = pkg_data.get('workspaces', [])
                for ws in workspaces:
                    result['modules'][ws] = {
                        'path': ws,
                        'key_classes': [],
                        'role': '',
                    }
            except json.JSONDecodeError:
                pass
        return result

    def _analyze_generic(self) -> Dict[str, Any]:
        """범용 프로젝트를 분석한다."""
        result: Dict[str, Any] = {'modules': {}}
        # 최상위 디렉토리를 모듈로 취급
        for child in sorted(self.project_path.iterdir()):
            if child.is_dir() and not child.name.startswith('.'):
                if child.name not in ('node_modules', 'build', 'dist',
                                      'target', '__pycache__', 'venv',
                                      'gradle', '.gradle', 'workspace'):
                    result['modules'][child.name] = {
                        'path': child.name,
                        'key_classes': [],
                        'role': '',
                    }
        return result

    # ── 모듈 분석 ─────────────────────────────────────────

    def _analyze_module(
        self, mod_path: Path, mod_name: str
    ) -> Dict[str, Any]:
        """개별 모듈의 구조와 핵심 클래스를 분석한다."""
        result: Dict[str, Any] = {
            'key_classes': [],
            'directories': [],
        }

        # 소스 루트 탐색
        src_root = self._find_source_root(mod_path)
        if not src_root or not src_root.exists():
            result['role'] = '빈 모듈 또는 소스 없음'
            return result

        # 디렉토리 구조 (adapter/application/domain 등)
        dirs = self._scan_directory_structure(src_root)
        result['directories'] = dirs

        # 핵심 클래스 탐색
        key_classes = []
        for pattern in self.KEY_FILE_PATTERNS:
            for f in src_root.rglob(pattern):
                class_info = self._extract_class_info(f)
                if class_info:
                    key_classes.append(class_info)

        result['key_classes'] = key_classes

        # 모듈 역할 추론 (디렉토리 + 클래스 기반)
        result['role'] = self._infer_module_role(mod_name, key_classes, dirs)

        # build.gradle 의존성
        build_gradle = mod_path / 'build.gradle'
        if build_gradle.exists():
            deps = self._extract_gradle_deps(build_gradle)
            if deps:
                result['dependencies'] = deps

        return result

    def _find_source_root(self, mod_path: Path) -> Optional[Path]:
        """모듈의 소스 루트를 찾는다."""
        # Java/Kotlin: src/main/java 또는 src/main/kotlin
        for lang_dir in ('java', 'kotlin'):
            src = mod_path / 'src' / 'main' / lang_dir
            if src.exists():
                return src

        # Python: src/ 또는 모듈 루트
        src = mod_path / 'src'
        if src.exists():
            return src

        # Node.js: src/ 또는 lib/
        for d in ('src', 'lib'):
            p = mod_path / d
            if p.exists():
                return p

        return None

    def _scan_directory_structure(self, src_root: Path) -> List[str]:
        """소스 루트 아래의 주요 디렉토리 목록을 반환한다."""
        dirs = []
        # 패키지 루트 찾기 (com/dailyword/xxx 등)
        for d in src_root.rglob('*'):
            if d.is_dir():
                rel = d.relative_to(src_root)
                depth = len(rel.parts)
                # 너무 깊은 건 스킵, 패키지 루트 아래 3단계까지
                if depth <= 6:
                    dirs.append(str(rel))
        return dirs

    def _extract_class_info(self, file_path: Path) -> Optional[Dict]:
        """Java/Kotlin 파일에서 클래스 정보를 추출한다."""
        try:
            content = file_path.read_text(errors='replace')
            lines = content.split('\n')[:30]  # 상위 30줄만

            class_name = file_path.stem
            rel_path = str(
                file_path.relative_to(self.project_path)
            )

            info: Dict[str, Any] = {
                'name': class_name,
                'path': rel_path,
            }

            # 패키지 추출
            for line in lines:
                pkg = re.match(r'package\s+([\w.]+)', line)
                if pkg:
                    info['package'] = pkg.group(1)
                    break

            # extends/implements 추출
            header = ' '.join(lines)
            extends = re.search(
                r'class\s+\w+\s+extends\s+(\w+)', header
            )
            if extends:
                info['extends'] = extends.group(1)

            implements = re.search(
                r'implements\s+([\w,\s]+?)[\s{]', header
            )
            if implements:
                impl_list = [
                    s.strip()
                    for s in implements.group(1).split(',')
                ]
                info['implements'] = impl_list

            # 어노테이션 추출 (Entity, RestController 등)
            annotations = re.findall(r'@(\w+)', header)
            notable = [
                a for a in annotations
                if a in (
                    'Entity', 'RestController', 'Controller',
                    'Service', 'Component', 'Repository',
                    'Configuration', 'FeignClient',
                    'MappedSuperclass', 'Table',
                )
            ]
            if notable:
                info['annotations'] = notable

            return info

        except Exception:
            return None

    def _extract_gradle_deps(self, build_gradle: Path) -> List[str]:
        """build.gradle에서 주요 의존성을 추출한다."""
        content = self._read_file_safe(str(
            build_gradle.relative_to(self.project_path)
        ))
        if not content:
            return []

        deps = re.findall(
            r"(?:implementation|api|compileOnly)\s+['\"]([^'\"]+)['\"]",
            content
        )
        return deps

    def _infer_module_role(
        self,
        mod_name: str,
        key_classes: List[Dict],
        dirs: List[str]
    ) -> str:
        """모듈 이름, 클래스, 디렉토리로 역할을 추론한다."""
        if not key_classes:
            return '빈 스켈레톤'

        class_names = [c['name'] for c in key_classes]
        annotations = []
        for c in key_classes:
            annotations.extend(c.get('annotations', []))

        # 이름 기반 추론
        if 'gateway' in mod_name.lower():
            return 'API 라우팅, 인증 필터, FeignClient'
        if 'auth' in mod_name.lower():
            return 'JWT 토큰 생성/검증/갱신'
        if 'member' in mod_name.lower():
            return '사용자 엔티티 관리'
        if 'common' in mod_name.lower():
            return '공통 엔티티, 유틸리티, 에러 코드'

        # 클래스 기반 추론
        roles = []
        if any('Entity' in n for n in class_names):
            roles.append('엔티티')
        if any('Facade' in n or 'Controller' in n for n in class_names):
            roles.append('API')
        if any('Service' in n for n in class_names):
            roles.append('비즈니스 로직')
        if any('Repository' in n for n in class_names):
            roles.append('데이터 접근')

        return ', '.join(roles) if roles else mod_name

    # ── 아키텍처/컨벤션 감지 ──────────────────────────────

    def _detect_architecture_pattern(
        self, modules: Dict[str, Any]
    ) -> str:
        """디렉토리 구조로 아키텍처 패턴을 감지한다."""
        all_dirs = []
        for mod in modules.values():
            all_dirs.extend(mod.get('directories', []))

        dirs_str = ' '.join(all_dirs).lower()

        if 'adapter' in dirs_str and 'domain' in dirs_str:
            if 'application' in dirs_str:
                return 'hexagonal (adapter/application/domain)'
            return 'hexagonal (adapter/domain)'

        if 'controller' in dirs_str and 'service' in dirs_str:
            if 'repository' in dirs_str:
                return 'layered (controller/service/repository)'
            return 'layered (controller/service)'

        return 'unknown'

    def _detect_package_convention(self) -> str:
        """패키지 네이밍 컨벤션을 감지한다."""
        # 아무 Java 파일에서 패키지 추출
        for f in self.project_path.rglob('*.java'):
            if '.git' in str(f) or 'workspace' in str(f):
                continue
            try:
                for line in f.read_text(errors='replace').split('\n')[:5]:
                    pkg = re.match(r'package\s+([\w.]+)', line)
                    if pkg:
                        # com.dailyword.auth → com.dailyword.{module}
                        parts = pkg.group(1).split('.')
                        if len(parts) >= 3:
                            return '.'.join(parts[:2]) + '.{module}'
                        return pkg.group(1)
            except Exception:
                continue
        return 'unknown'

    # ── 동적 타겟 컨텍스트 (2단계) ───────────────────────

    def _find_relevant_modules(
        self,
        profile: Dict[str, Any],
        spec_content: str
    ) -> List[str]:
        """기획서에서 언급된 관련 모듈을 찾는다."""
        spec_lower = spec_content.lower()
        modules = profile.get('modules', {})
        relevant = []

        for mod_name in modules:
            # 모듈 이름이 기획서에 언급되었는지
            if mod_name.lower() in spec_lower:
                relevant.append(mod_name)
            # 하이픈 제거 버전 확인 (module-auth → moduleauth)
            elif mod_name.replace('-', '') in spec_lower.replace('-', ''):
                relevant.append(mod_name)

        # common은 항상 포함 (공통 베이스 클래스)
        if 'common' in modules and 'common' not in relevant:
            relevant.append('common')

        logger.info(f"관련 모듈 추출: {relevant}")
        return relevant

    def _format_overview(self, profile: Dict[str, Any]) -> str:
        """프로젝트 개요 섹션을 포맷한다."""
        pt = profile.get('project_type', {})
        arch = profile.get('architecture_pattern', 'unknown')
        pkg = profile.get('package_convention', 'unknown')

        lines = ['## 프로젝트 컨텍스트 (사전 분석 결과)', '']
        lines.append(f"- **프로젝트**: {profile.get('project_name', '?')}")
        lines.append(
            f"- **타입**: {pt.get('framework', '?')} "
            f"({pt.get('language', '?')}, "
            f"{pt.get('build_system', '?')})"
        )
        if pt.get('framework_version'):
            lines.append(
                f"- **프레임워크 버전**: {pt['framework_version']}"
            )
        if pt.get('java_version'):
            lines.append(f"- **Java 버전**: {pt['java_version']}")
        lines.append(f"- **아키텍처**: {arch}")
        lines.append(f"- **패키지 규칙**: {pkg}")

        return '\n'.join(lines)

    def _format_module_table(self, profile: Dict[str, Any]) -> str:
        """모듈 구조 테이블을 포맷한다."""
        modules = profile.get('modules', {})
        if not modules:
            return ''

        lines = ['### 모듈 구조', '']
        lines.append('| 모듈 | 역할 | 주요 클래스 |')
        lines.append('|------|------|------------|')

        for name, info in sorted(modules.items()):
            role = info.get('role', '-')
            classes = [c['name'] for c in info.get('key_classes', [])[:5]]
            classes_str = ', '.join(classes) if classes else '-'
            lines.append(f"| {name} | {role} | {classes_str} |")

        return '\n'.join(lines)

    def _format_relevant_code(
        self,
        profile: Dict[str, Any],
        relevant_modules: List[str],
        max_lines: int
    ) -> str:
        """관련 모듈의 핵심 코드를 시그니처 형태로 포맷한다."""
        modules = profile.get('modules', {})
        sections = ['### 관련 코드 (시그니처)', '']

        for mod_name in relevant_modules:
            mod_info = modules.get(mod_name, {})
            key_classes = mod_info.get('key_classes', [])

            if not key_classes:
                continue

            sections.append(f'#### {mod_name}/')

            for cls in key_classes[:8]:  # 모듈당 최대 8개 파일
                file_path = self.project_path / cls['path']
                if not file_path.exists():
                    continue

                try:
                    # 시그니처만 추출
                    signature_info = self._extract_signatures(file_path)

                    sections.append(f"\n**{cls['name']}** (`{cls['path']}`)")

                    # 패키지
                    if signature_info.get('package'):
                        sections.append(f"Package: `{signature_info['package']}`")

                    # 어노테이션
                    if cls.get('annotations'):
                        sections.append(f"Annotations: @{', @'.join(cls['annotations'])}")

                    # 상속/구현
                    if cls.get('extends'):
                        sections.append(f"Extends: `{cls['extends']}`")
                    if cls.get('implements'):
                        sections.append(f"Implements: `{', '.join(cls['implements'])}`")

                    # 필드 (시그니처만)
                    if signature_info.get('fields'):
                        sections.append("\nFields:")
                        for field in signature_info['fields'][:10]:  # 최대 10개
                            annotations = ' '.join(f"@{a}" for a in field.get('annotations', []))
                            sections.append(f"  {annotations} {field['type']} {field['name']}")

                    # 메서드 (시그니처만)
                    if signature_info.get('methods'):
                        sections.append("\nMethods:")
                        for method in signature_info['methods'][:15]:  # 최대 15개
                            annotations = ' '.join(f"@{a}" for a in method.get('annotations', []))
                            sections.append(f"  {annotations} {method['signature']}")

                    sections.append('')

                except Exception as e:
                    logger.debug(f"시그니처 추출 실패 {file_path}: {e}")
                    continue

            sections.append('')

        return '\n'.join(sections)

    def _extract_signatures(self, file_path: Path) -> Dict[str, Any]:
        """Java 파일에서 필드와 메서드 시그니처만 추출한다."""
        try:
            content = file_path.read_text(errors='replace')
        except Exception:
            return {}

        signatures = {
            'package': self._extract_package_name(content),
            'fields': self._extract_field_signatures(content),
            'methods': self._extract_method_signatures_detailed(content),
        }

        return signatures

    def _extract_package_name(self, content: str) -> Optional[str]:
        """패키지명 추출."""
        match = re.search(r'package\s+([\w.]+);', content)
        return match.group(1) if match else None

    def _extract_field_signatures(self, content: str) -> List[Dict]:
        """필드 시그니처 추출 (타입, 이름, 어노테이션만).

        단순화된 접근: 클래스 depth 추적 대신 패턴 매칭만 사용.
        일부 false positive는 허용 (큰 문제 아님).
        """
        fields = []

        try:
            # 주석 제거 (간단히)
            content = re.sub(r'//.*', '', content)  # 한 줄 주석
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)  # 블록 주석

            # 필드 패턴: (접근제어자) (modifiers) (타입) (이름);
            # 간단하게: private/public/protected로 시작하고 ( 없고 ; 또는 = 있음
            pattern = r'''
                ((?:@\w+(?:\([^)]*\))?\s+)*)      # 어노테이션들 (선택)
                (private|protected|public)\s+     # 접근제어자
                ((?:static|final)\s+)*            # modifiers (선택)
                ([\w<>[\].,?\s]+)\s+              # 타입 (제네릭 포함)
                (\w+)                             # 필드 이름
                \s*[;=]                           # ; 또는 = 로 끝남
            '''

            for match in re.finditer(pattern, content, re.VERBOSE):
                annotations_raw = match.group(1) or ''
                type_name = match.group(4).strip()
                field_name = match.group(5)

                # ( 가 있으면 메서드일 가능성 높음 → 스킵
                if '(' in match.group(0):
                    continue

                # 어노테이션 추출
                annotations = re.findall(r'@(\w+)', annotations_raw)

                fields.append({
                    'type': type_name,
                    'name': field_name,
                    'annotations': annotations
                })

        except Exception as e:
            logger.debug(f"필드 추출 중 에러 (무시): {e}")

        return fields[:20]  # 최대 20개로 제한

    def _extract_method_signatures_detailed(self, content: str) -> List[Dict]:
        """메서드 시그니처 추출 (구현부 제외, getter/setter 필터링).

        단순화된 접근: 복잡한 파싱 대신 패턴 매칭 위주.
        일부 false positive/negative는 허용 (큰 문제 아님).
        """
        methods = []

        try:
            # 주석 제거 (// 및 /* */)
            content = re.sub(r'//.*', '', content)
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

            # 메서드 패턴
            # (어노테이션) (접근제어자) (modifiers) (리턴타입) (메서드명) (파라미터)
            pattern = r'''
                (@\w+(?:\([^)]*\))?\s*)*          # 어노테이션들
                (public|private|protected)\s+     # 접근 제어자
                (static\s+|final\s+)*             # static, final
                ([\w<>[\],\s]+)\s+                # 리턴 타입
                (\w+)\s*                          # 메서드 이름
                \(([^)]*)\)                       # 파라미터
                \s*(?:throws\s+[\w\s,]+)?         # throws (선택)
                \s*[{;]                           # { 또는 ; (인터페이스)
            '''

            for match in re.finditer(pattern, content, re.VERBOSE | re.MULTILINE):
                annotations_raw = match.group(1) or ''
                access = match.group(2)
                modifiers = (match.group(3) or '').strip()
                return_type = match.group(4).strip()
                method_name = match.group(5)
                params = match.group(6).strip()

                # 어노테이션 파싱
                annotations = re.findall(r'@(\w+)', annotations_raw)

                # getter/setter 제외 (중요한 어노테이션 있으면 포함)
                is_getter_setter = (
                    method_name.startswith('get') or
                    method_name.startswith('set') or
                    method_name.startswith('is')
                )

                important_annotations = {
                    'Transactional', 'PostMapping', 'GetMapping',
                    'PutMapping', 'DeleteMapping', 'PatchMapping',
                    'RequestMapping', 'Override', 'Bean',
                    'PreAuthorize', 'PostAuthorize', 'Async'
                }

                has_important = any(ann in important_annotations for ann in annotations)

                # getter/setter이면서 중요한 어노테이션 없으면 스킵
                if is_getter_setter and not has_important:
                    continue

                # 시그니처 조립
                sig_parts = [access]
                if modifiers:
                    sig_parts.append(modifiers)
                sig_parts.extend([return_type, method_name + '(' + params + ')'])

                signature = ' '.join(sig_parts)
                signature = re.sub(r'\s+', ' ', signature)  # 공백 정리

                methods.append({
                    'name': method_name,
                    'signature': signature,
                    'return_type': return_type,
                    'annotations': annotations,
                    'is_important': not is_getter_setter or has_important
                })

        except Exception as e:
            logger.debug(f"메서드 추출 중 에러 (무시): {e}")

        return methods[:25]  # 최대 25개로 제한

    # ── 유틸리티 ──────────────────────────────────────────

    def _get_current_commit(self) -> str:
        """현재 HEAD의 commit SHA를 반환한다."""
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%H'],
                cwd=self.project_path,
                capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip() or 'unknown'
        except Exception:
            return 'unknown'

    def _get_changed_files(
        self, old_commit: str, new_commit: str
    ) -> List[str]:
        """두 커밋 사이 변경된 파일 목록을 반환한다."""
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', old_commit, new_commit],
                cwd=self.project_path,
                capture_output=True, text=True, timeout=10
            )
            return [f for f in result.stdout.strip().split('\n') if f]
        except Exception:
            return []

    def _read_file_safe(self, relative_path: str) -> Optional[str]:
        """파일을 안전하게 읽는다."""
        try:
            return (self.project_path / relative_path).read_text(
                errors='replace'
            )
        except Exception:
            return None

    def _load_profile(self) -> Optional[Dict[str, Any]]:
        """기존 프로필을 로드한다."""
        if not self.profile_path.exists():
            return None
        try:
            return json.loads(self.profile_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _save_profile(self, profile: Dict[str, Any]) -> None:
        """프로필을 저장한다."""
        try:
            self.profile_path.write_text(
                json.dumps(profile, ensure_ascii=False, indent=2)
            )
            logger.info(f"프로젝트 프로필 저장: {self.profile_path}")
        except OSError as e:
            logger.warning(f"프로필 저장 실패: {e}")
