#!/usr/bin/env python3
from typing import Iterable
import os
import asyncio
import subprocess
import json
import argparse
from pathlib import Path


def vswhere(*args) -> list[dict]:
    vswhere_path = Path(os.environ["ProgramFiles(x86)"])/"Microsoft Visual Studio"/"Installer"/"vswhere"
    p = subprocess.Popen([vswhere_path, *args, "-format", "json"], stdout=subprocess.PIPE)
    out = json.load(p.stdout) # type: ignore
    if p.wait() != 0:
        raise Exception(f"ERROR: vswhere failed with code 0x{p.returncode:x}")
    return out

def _identify_msvc_packages(packages: Iterable[dict]) -> Iterable[tuple[str, str, str]]:
    for package in packages:
        id = package['id']
        if (id.startswith("Microsoft.VisualCpp.Tools.Host") or
            id.startswith("Microsoft.VC.") or
            id.startswith("Microsoft.VisualC.")):
            _, tools, arch = id.partition(".Tools.Host")
            if tools:
                host_arch, target, target_arch = arch.partition(".Target")
                if not target:
                    raise Exception(f"unknown VC package ID format '{id}'")
                target_arch, dot, _ = target_arch.partition('.')
                if not dot:
                    version, _, _ = package['version'].rpartition('.')
                    yield version, host_arch.lower(), target_arch.lower()

class MSVCToolchainVisitor:
    def visit_toolchain(self, version: str, host_arch: str, target_arch: str) -> None:
        pass

class VSitor:
    def visit_product(self, name: str, version: str, vcvarsall: os.PathLike) -> MSVCToolchainVisitor | None:
        pass

def visit_VS(visitor: VSitor, *, prerelease: bool = True) -> VSitor:
    products = vswhere("-all", *(("-prerelease",) if prerelease else ()), "-products", "*", "-include", "packages")
    for product in products:
        if product['isComplete']:
            toolchain_visitor = visitor.visit_product(
                product['displayName'],
                product['installationVersion'],
                Path(product["installationPath"])/"VC"/"Auxiliary"/"Build"/"vcvarsall.bat")
            if toolchain_visitor:
                for version, host_arch, target_arch in sorted(set(_identify_msvc_packages(product['packages']))):
                    toolchain_visitor.visit_toolchain(version, host_arch, target_arch)
    return visitor

# def _consume_cl_version_line(f):
#     l = f.readline()
#     if not l:
#         raise Exception("failed to read cl.exe version line")
#     f.read()
#     return codecs.decode(l).strip()

# def getCLVersion(cl):
#     with subprocess.Popen([cl], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as p:
#         l = _consume_cl_version_line(p.stderr).split(' ')

#         if p.wait() != 0:
#             raise Exception("cl.exe failed")

#         if len(l) != 9:
#             raise Exception("unknown cl.exe output format")

#         return l[-3], l[-1]

# class MSVCConfig:
#     def write(self, file):
#         file.write(
#             f"compiler.{self.id}.name={self.name}\n"
#             f"compiler.{self.id}.exe={self.cl}\n"
#             f"compiler.{self.id}.includePath={self.include_paths}\n"
#             f"compiler.{self.id}.libPath={self.lib_paths}\n"
#             f"compiler.{self.id}.demangler={self.undname}\n"
#         )

# def _iterate_compiler_config_echo(f):
#     lines = _iterate_lines(f)
#     for l in lines:
#         if l == '--{':
#             break
#     for l in lines:
#         if l == '}--':
#             break
#         yield l
#     f.read()

async def _detectCompilerConfig(vcvarsall: str, version: str, host_arch: str, target_arch: str) -> None:
#     echo_msvc_config_path = _this_dir/"echo_msvc_config.bat"
#     with subprocess.Popen(["cmd", "/C", str(vcvarsall), platform, "&&", str(echo_msvc_config_path)], stdout=subprocess.PIPE) as p:
#         echo = [s for s in _iterate_compiler_config_echo(p.stdout)]

#         if p.wait() != 0:
#             raise Exception("echo_msvc_config failed")

#         if len(echo) != 4:
#             raise Exception("failed to detect compiler config")

#         cfg = MSVCConfig()
#         cfg.cl = echo[0]
#         cfg.include_paths = echo[1]
#         cfg.lib_paths = echo[2]
#         cfg.undname = echo[3]
#         cfg.version, cfg.platform = getCLVersion(cfg.cl)
#         cfg.id = f"msvc_{cfg.version.replace('.', '_')}_{cfg.platform}"
#         cfg.name = f"MSVC {cfg.version} {cfg.platform}"

#         return cfg
    p = await asyncio.subprocess.create_subprocess_exec("cmd", "/C", vcvarsall, f"{host_arch}_{target_arch}", f"vcvars_ver={version}")


# def detectMSVCConfigs(instance, platforms, *, verbose=True):
#     name = instance["displayName"]
#     version = instance["installationVersion"]
#     inst_path = Path(instance["installationPath"])

#     if verbose:
#         print(f"found {name} ({version}) in {inst_path}")

#     vcvarsall = inst_path/"VC"/"Auxiliary"/"Build"/"vcvarsall.bat"

#     for platform in platforms:
#         cfg = _detectCompilerConfig(vcvarsall, platform)

#         if verbose:
#             print(f"\t{cfg.name}")

#         yield cfg


# def generateConfig(file, platforms, *, prerelease=True):
#     instances = getVSInstances(prerelease=prerelease)

#     configs = []

#     for instance in instances:
#         file.write(f"# {instance['installationName']}\n")

#         for cfg in detectMSVCConfigs(instance, platforms):
#             configs.append(cfg)
#             cfg.write(file)
#             file.write('\n')

#     file.write("# MSVC target platform groups\n")
#     for platform in platforms:
#         compilers = [cfg.id for cfg in configs if cfg.platform == platform]
#         file.write(f"group.msvc_{platform}.groupName=MSVC {platform}\n")
#         file.write(f"group.msvc_{platform}.compilers={':'.join(compilers)}\n")
#         file.write('\n')

#     file.write("# MSVC common properties\n")
#     file.write(f"group.msvc.groupName=MSVC\n")
#     file.write(f"group.msvc.options=-EHsc\n")
#     file.write(f"group.msvc.includeFlag=/I\n")
#     file.write(f"group.msvc.needsMulti=false\n")
#     file.write(f"group.msvc.compilerType=win32-vc\n")
#     file.write(f"group.msvc.compilers={':'.join([f'&msvc_{p}' for p in platforms])}\n")
#     file.write('\n')
#     if configs:
#         file.write(f"defaultCompiler={configs[0].id}\n")
#         file.write('\n')
#     file.write(f"compilers=&msvc\n")

class MSVCCollector(VSitor, MSVCToolchainVisitor):
    def __init__(self, *, include_host_arch = None, include_target_arch = None):
        self.include_host_arch = include_host_arch
        self.include_target_arch = include_target_arch

    def visit_product(self, name: str, version: str, vcvarsall: os.PathLike):
        print("found", name, version)
        self.vcvarsall = vcvarsall
        return self

    def visit_toolchain(self, version: str, host_arch: str, target_arch: str):
        if self.include_host_arch and host_arch not in self.include_host_arch:
            return
        if self.include_target_arch and target_arch not in self.include_target_arch:
            return
        print(f"\t{version} {host_arch} -> {target_arch} {self.vcvarsall}")


def main(args):
    this_dir = Path(__file__).parent.resolve()

    collector = visit_VS(
        MSVCCollector(include_host_arch=args.host_arch, include_target_arch=args.target_arch), prerelease=args.prerelease)

    # if not args.platform:
    #     # TODO: properly deal with picking the right compiler version given the host architecture
    #     args.platform = ["x64", "x86"]

    # with open(_this_dir.parent/"etc"/"config"/"c++.local.properties", "wt") as file:
    #     generateConfig(file, args.platform, prerelease=args.prerelease)


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-host", "--host-arch", action="append", type=str.lower, help="only include the given host architectures")
    argparser.add_argument("-target", "--target-arch", action="append", type=str.lower, help="only include the given target architectures")
    argparser.add_argument("-nopreview", "--no-prerelease", action="store_false", dest="prerelease", help="ignore preview builds")
    main(argparser.parse_args())
