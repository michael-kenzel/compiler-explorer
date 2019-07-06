#!/usr/bin/env python3

import sys
import os
import subprocess
import codecs
import argparse
from pathlib import Path


_this_dir = Path(__file__).parent.resolve()


def _iterate_lines(f):
	for l in f.readlines():
		yield codecs.decode(l).strip()


def vswhere(*args, **kwargs):
	vs_where_path = Path(os.environ["ProgramFiles(x86)"])/"Microsoft Visual Studio"/"Installer"/"vswhere"
	return subprocess.Popen([str(vs_where_path), *args], **kwargs)

def getVSInstances():
	with vswhere("-nologo", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-sort", stdout=subprocess.PIPE) as p:
		props = [{}]
		for l in _iterate_lines(p.stdout):
			if l:
				k, v = l.split(':', 1)
				props[-1][k] = v.strip()
			else:
				props.append({})

		if p.wait() != 0:
			raise Exception("vswhere failed")

		return props


def _consume_cl_version_line(f):
	l = f.readline()
	if not l:
		raise Exception("failed to read cl.exe version line")
	f.read()
	return codecs.decode(l).strip()

def getCLVersion(cl):
	with subprocess.Popen([cl], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as p:
		l = _consume_cl_version_line(p.stderr).split(' ')

		if p.wait() != 0:
			raise Exception("cl.exe failed")

		if len(l) != 9:
			raise Exception("unknown cl.exe output format")

		return l[-3], l[-1]

class MSVCConfig:
	pass

def _iterate_compiler_config_echo(f):
	lines = _iterate_lines(f)
	for l in lines:
		if l == '--{':
			break
	for l in lines:
		if l == '}--':
			break
		yield l
	f.read()

def detectCompilerConfig(vcvarsall, platform):
	echo_msvc_config_path = _this_dir/"echo_msvc_config.bat"
	with subprocess.Popen(["cmd", "/C", str(vcvarsall), platform, "&&", str(echo_msvc_config_path)], stdout=subprocess.PIPE) as p:
		echo = [s for s in _iterate_compiler_config_echo(p.stdout)]

		if p.wait() != 0:
			raise Exception("echo_msvc_config failed")

		if len(echo) != 4:
			raise Exception("failed to detect compiler config")

		cfg = MSVCConfig()
		cfg.cl = echo[0]
		cfg.include_paths = echo[1]
		cfg.lib_paths = echo[2]
		cfg.undname = echo[3]
		cfg.version, cfg.platform = getCLVersion(cfg.cl)
		cfg.name = f"msvc_{cfg.version.replace('.', '_')}_{cfg.platform}"
		cfg.pretty_name = f"MSVC {cfg.version} {cfg.platform}"

		return cfg


def detectMSVCConfigs(platforms):
	for props in getVSInstances():
		pretty_name = props["displayName"]
		version = props["installationVersion"]
		inst_path = Path(props["installationPath"])

		print(f"found {pretty_name} ({version}) in {inst_path}")

		vcvarsall = inst_path/"VC"/"Auxiliary"/"Build"/"vcvarsall.bat"

		for platform in platforms:
			yield detectCompilerConfig(vcvarsall, platform)


def main(args):
	if not args.platform:
		args.platform = ["x86", "amd64"]

	# with open(_this_dir/"c++.local.properties", "wt") as file:

	for cfg in detectMSVCConfigs(args.platform):
		print("found", cfg.pretty_name)
		# print(f"compiler.{cfg.name}.exe={cfg.cl}")
		# print(f"compiler.{cfg.name}.includePath={cfg.include_paths}")
		# print(f"compiler.{cfg.name}.libPath={cfg.lib_paths}")
		# print(f"compiler.{cfg.name}.demangler={cfg.undname}")
		# print(f"compiler.{cfg.name}.name={cfg.pretty_name}")


if __name__ == "__main__":
	argparser = argparse.ArgumentParser()
	argparser.add_argument("-platform", "--platform", action="append")
	main(argparser.parse_args())
