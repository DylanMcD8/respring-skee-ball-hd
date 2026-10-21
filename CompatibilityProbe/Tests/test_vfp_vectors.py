"""Compile the production VFP decoder methods in a dependency-free Rust harness."""
from pathlib import Path
import os, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
source = (root / 'compatibility-core/src/cpu/interpreter/vfp.rs').read_text()
def function(name):
    start = source.index('fn ' + name + '(')
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]
methods = '\n'.join(function(n) for n in ['vfp_data_proc', 'vfp_data_proc_scalar', 'vfp_other'])
helpers = '\n'.join(function(n) for n in ['vfp_expand_imm32', 'vfp_expand_imm64', 'fp_cmp_flags', 'fp_to_i32', 'fp_to_u32'])
harness = r'''
#![allow(dead_code)]
#[derive(Debug,PartialEq)] enum CpuState { Normal }
struct InterpreterCpu { regs:[u32;16], extregs:[u32;64], fpscr:u32 }
impl InterpreterCpu {
fn new()->Self { Self { regs:[0;16],extregs:[0;64],fpscr:3<<16 } }
fn get_sreg(&self,r:usize)->u32 {self.extregs[r]}
fn set_sreg(&mut self,r:usize,v:u32){self.extregs[r]=v;}
fn get_s_f32(&self,r:usize)->f32{f32::from_bits(self.get_sreg(r))}
fn set_s_f32(&mut self,r:usize,v:f32){self.set_sreg(r,v.to_bits());}
fn get_dreg(&self,r:usize)->u64{self.extregs[r*2] as u64|((self.extregs[r*2+1] as u64)<<32)}
fn set_dreg(&mut self,r:usize,v:u64){self.extregs[r*2]=v as u32;self.extregs[r*2+1]=(v>>32) as u32;}
fn get_d_f64(&self,r:usize)->f64{f64::from_bits(self.get_dreg(r))}
fn set_d_f64(&mut self,r:usize,v:f64){self.set_dreg(r,v.to_bits());}
METHODS
}
HELPERS
#[test] fn unity_batched_vertex_transform() {
 let mut c=InterpreterCpu::new();
 for (i,v) in [2.,0.,0.,0.,0.,3.,0.,0.,0.,0.,4.,0.,10.,20.,30.,1.].into_iter().enumerate(){c.set_s_f32(16+i,v);}
 for (i,v) in [1.,2.,3.].into_iter().enumerate(){c.set_s_f32(i,v);}
 // Actual instructions from Skee-Ball HD's ARMv6 TransformVerts routine.
 for insn in [0xeeb04a4e,0xee084a00,0xee0a4a20,0xee0c4a01]{assert_eq!(c.vfp_data_proc(insn,0x1000),Some(CpuState::Normal));}
 assert_eq!((8..12).map(|r|c.get_s_f32(r)).collect::<Vec<_>>(),[12.,26.,42.,1.]);
 assert_eq!(c.fpscr,3<<16);assert_eq!(c.regs[15],0x1004);
}
#[test] fn stride_two_wraps_within_bank() {
 let mut c=InterpreterCpu::new();c.fpscr|=1<<20;c.set_s_f32(0,1.);
 for i in 0..8 {c.set_s_f32(16+i,i as f32);c.set_s_f32(8+i,-99.);}
 assert_eq!(c.vfp_data_proc(0xee7b7a80,0),Some(CpuState::Normal));
 assert_eq!([15,9,11,13].map(|r|c.get_s_f32(r)),[8.,2.,4.,6.]);
 assert_eq!([8,10,12,14].map(|r|c.get_s_f32(r)),[-99.;4]);
}
#[test] fn scalar_destination_ignores_vector_length() {
 let mut c=InterpreterCpu::new();c.set_s_f32(16,2.);c.set_s_f32(24,3.);c.set_s_f32(1,77.);
 assert_eq!(c.vfp_data_proc(0xee380a0c,0),Some(CpuState::Normal));
 assert_eq!(c.get_s_f32(0),5.);assert_eq!(c.get_s_f32(1),77.);
}
#[test] fn scalar_source_broadcast_and_double_vectors() {
 let mut c=InterpreterCpu::new();c.set_s_f32(0,7.);
 assert_eq!(c.vfp_data_proc(0xeeb04a40,0),Some(CpuState::Normal));
 assert_eq!((8..12).map(|r|c.get_s_f32(r)).collect::<Vec<_>>(),[7.;4]);
 c.set_d_f64(0,2.);for i in 0..4 {c.set_d_f64(8+i,(i+2) as f64);}
 assert_eq!(c.vfp_data_proc(0xee284b00,0),Some(CpuState::Normal));
 assert_eq!((4..8).map(|r|c.get_d_f64(r)).collect::<Vec<_>>(),[4.,6.,8.,10.]);
}
#[test] fn conversion_stays_scalar_with_len_set() {
 let mut c=InterpreterCpu::new();c.set_s_f32(15,320.);c.set_s_f32(8,77.);
 assert_eq!(c.vfp_data_proc(0xeefc7ae7,0),Some(CpuState::Normal));
 assert_eq!(c.get_sreg(15),320);assert_eq!(c.get_s_f32(8),77.);
}
'''.replace('METHODS', methods).replace('HELPERS', helpers)
rustc = os.environ.get('RUSTC', 'rustc')
with tempfile.TemporaryDirectory(prefix='skeehd-vfp-tests-') as folder:
    path=Path(folder);(path/'tests.rs').write_text(harness)
    subprocess.run([rustc,'--edition=2021','--test',str(path/'tests.rs'),'-o',str(path/'tests')],check=True)
    subprocess.run([str(path/'tests')],check=True)
