#include "glog/logging.h"
#include "gtest/gtest.h"
#include "paddle/operators/functors/add_op_functor.h"
#include "paddle/operators/functors/mul_op_functor.h"
#include "paddle/operators/functors/softmax_op_functor.h"
#ifndef PADDLE_ONLY_CPU
#include "cuda_runtime.h"
#ifndef EIGEN_USE_GPU
#define EIGEN_USE_GPU
#endif
#endif

#include <cmath>
#include <iostream>
#include "Eigen/Core"
#include "Eigen/Dense"
#include "unsupported/Eigen/CXX11/Tensor"

using namespace paddle::framework;
using namespace paddle::platform;
using namespace paddle::operators;

template <typename T>
using Matrix =
    Eigen::TensorMap<Eigen::Tensor<T, 2, Eigen::RowMajor, Eigen::DenseIndex>,
                     Eigen::Aligned>;
TEST(OpFunctor, AddGPU) {
  int size = 4;

  float* t_a = (float*)malloc(size * sizeof(float));
  float* t_b = (float*)malloc(size * sizeof(float));
  float* t_c = (float*)malloc(size * sizeof(float));
  for (int i = 0; i < size; i++) {
    t_a[i] = i;
    t_b[i] = i;
  }

  Tensor t1;
  t1.mutable_data<float>({4}, GPUPlace(0));

  Tensor t2;
  t2.mutable_data<float>({4}, GPUPlace(0));

  Tensor t3;
  t3.mutable_data<float>({4}, GPUPlace(0));

  cudaMemcpy(
      t1.data<float>(), t_a, size * sizeof(float), cudaMemcpyHostToDevice);
  cudaMemcpy(
      t2.data<float>(), t_b, size * sizeof(float), cudaMemcpyHostToDevice);

  functors::add<GPUPlace, float> functor;

  DeviceContext* device = new CUDADeviceContext(0);

  functor(*device, t1, t2, &t3);

  cudaMemcpy(
      t_c, t3.data<float>(), size * sizeof(float), cudaMemcpyDeviceToHost);

  EXPECT_EQ(t_c[0], 0);
  EXPECT_EQ(t_c[1], 2);
  EXPECT_EQ(t_c[2], 4);
  EXPECT_EQ(t_c[3], 6);
}
TEST(OpFunctor, Mul) {
  LOG(INFO) << paddle::platform::GetCurrentDeviceId();
  int size = 4;

  float* t_a = (float*)malloc(size * sizeof(float));
  float* t_b = (float*)malloc(size * sizeof(float));
  float* t_c = (float*)malloc(size * sizeof(float));
  for (int i = 0; i < size; i++) {
    t_a[i] = i;
    t_b[i] = i;
  }

  float* d_a;
  float* d_b;
  float* d_c;
  cudaMalloc((void**)&d_a, size * sizeof(float));
  cudaMalloc((void**)&d_b, size * sizeof(float));
  cudaMalloc((void**)&d_c, size * sizeof(float));

  cudaMemcpy(d_a, t_a, size * sizeof(float), cudaMemcpyHostToDevice);
  cudaMemcpy(d_b, t_b, size * sizeof(float), cudaMemcpyHostToDevice);

  Matrix<float> a(d_a, 2, 2);
  Matrix<float> b(d_b, 2, 2);
  Matrix<float> c(d_c, 2, 2);

  Eigen::CudaStreamDevice sd;
  Eigen::GpuDevice dd(&sd);
  Eigen::array<Eigen::IndexPair<Eigen::DenseIndex>, 1> dim_pair;
  dim_pair[0].first = 1;
  dim_pair[0].second = 0;
  LOG(INFO) << "before mul";
  c.device(dd) = a.contract(b, dim_pair);
  LOG(INFO) << "after mul";
  cudaMemcpy(t_c, d_c, size * sizeof(float), cudaMemcpyDeviceToHost);

  EXPECT_EQ(t_c[0], 2);
  EXPECT_EQ(t_c[1], 3);
  EXPECT_EQ(t_c[2], 6);
  EXPECT_EQ(t_c[3], 11);
}
/*
TEST(OpFunctor, MulGPU) {
  int size = 4;
  float* t_a = (float*)malloc(size * sizeof(float));
  float* t_b = (float*)malloc(size * sizeof(float));
  float* t_c = (float*)malloc(size * sizeof(float));
  for (int i = 0; i < size; i++) {
    t_a[i] = i;
    t_b[i] = i;
  }
  Tensor t1;
  t1.mutable_data<float>({2, 2}, GPUPlace(0));
  Tensor t2;
  t2.mutable_data<float>({2, 2}, GPUPlace(0));
  Tensor t3;
  t3.mutable_data<float>({2, 2}, GPUPlace(0));
  cudaMemcpy(
      t1.data<float>(), t_a, size * sizeof(float), cudaMemcpyHostToDevice);
  cudaMemcpy(
      t2.data<float>(), t_b, size * sizeof(float), cudaMemcpyHostToDevice);
  functors::mul<GPUPlace, float> functor;
  DeviceContext* device = new CUDADeviceContext(0);
  functor(*device, t1, t2, &t3);
  cudaMemcpy(
      t_c, t3.data<float>(), size * sizeof(float), cudaMemcpyDeviceToHost);
  EXPECT_EQ(t_c[0], 2);
  EXPECT_EQ(t_c[1], 3);
  EXPECT_EQ(t_c[2], 6);
  EXPECT_EQ(t_c[3], 11);
}
*/
