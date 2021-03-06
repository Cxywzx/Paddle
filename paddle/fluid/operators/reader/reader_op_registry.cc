//   Copyright (c) 2018 PaddlePaddle Authors. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "reader_op_registry.h"

namespace paddle {
namespace operators {
namespace reader {

std::vector<framework::DDim> RestoreShapes(const std::vector<int>& shape_concat,
                                           const std::vector<int>& ranks) {
  std::vector<framework::DDim> res;
  int offset = 0;
  for (int len : ranks) {
    auto start_it = shape_concat.begin() + offset;
    auto end_it = start_it + len;
    res.push_back(framework::make_ddim(std::vector<int>(start_it, end_it)));
    offset += len;
  }
  return res;
}

FileReaderMakerBase::FileReaderMakerBase(
    framework::OpProtoAndCheckerMaker::OpProto* op_proto,
    framework::OpAttrChecker* op_checker)
    : OpProtoAndCheckerMaker(op_proto, op_checker) {
  AddOutput("Out", "(ReaderHolder) The created random reader.");
  AddAttr<std::vector<int>>("shape_concat", "The concat of all data's shapes.");
  AddAttr<std::vector<int>>(
      "ranks",
      "The ranks of each data."
      "e.g."
      "shape_concat = [2,3,4,5,6]"
      "ranks = [3,2]"
      "It means the reader will generate two data each time,"
      "whose shapes are [2,3,4] and [5,6] respectively.");
  AddAttr<std::vector<int>>("lod_levels", "The LoD levels of each data.");
}

void FileReaderInferShape::operator()(framework::InferShapeContext* ctx) const {
  PADDLE_ENFORCE(
      !ctx->IsRuntime(),
      "'FileReaderInferShape' should only be invoked during compile time.");

  PADDLE_ENFORCE(ctx->HasOutput("Out"),
                 "The output file reader should not be null.");
  const auto shape_concat = ctx->Attrs().Get<std::vector<int>>("shape_concat");
  const auto ranks = ctx->Attrs().Get<std::vector<int>>("ranks");
  std::vector<framework::DDim> shapes = RestoreShapes(shape_concat, ranks);
  ctx->SetReaderDims("Out", shapes);

  const auto lod_levels = ctx->Attrs().Get<std::vector<int>>("lod_levels");
  PADDLE_ENFORCE_EQ(lod_levels.size(), shapes.size(),
                    "The number of 'lod_levels'(%d) doesn't match the number "
                    "of 'shapes'(%d).",
                    lod_levels.size(), shapes.size());
  framework::VarDesc* reader =
      boost::get<framework::VarDesc*>(ctx->GetOutputVarPtrs("Out")[0]);
  reader->SetLoDLevels(lod_levels);
}

void FileReaderInferVarType::operator()(const framework::OpDesc& op_desc,
                                        framework::BlockDesc* block) const {
  std::string reader_name = op_desc.Output("Out")[0];
  framework::VarDesc* reader = block->FindVarRecursive(reader_name);
  reader->SetType(framework::proto::VarType::READER);
}

void DecoratedReaderInferShape::operator()(
    framework::InferShapeContext* ctx) const {
  PADDLE_ENFORCE(!ctx->IsRuntime(),
                 "'DecoratedReaderInferShape' should only be invoked during "
                 "compile time.");

  PADDLE_ENFORCE(ctx->HasInput("UnderlyingReader"),
                 "Input(UnderlyingReader) should not be null.");
  PADDLE_ENFORCE(ctx->HasOutput("Out"),
                 "The output decorated reader should not be null.");
  ctx->SetReaderDims("Out", ctx->GetReaderDims("UnderlyingReader"));

  framework::VarDesc* in_reader = boost::get<framework::VarDesc*>(
      ctx->GetInputVarPtrs("UnderlyingReader")[0]);
  framework::VarDesc* out_reader =
      boost::get<framework::VarDesc*>(ctx->GetOutputVarPtrs("Out")[0]);
  out_reader->SetLoDLevels(in_reader->GetLoDLevels());
}
void DecoratedReaderInferVarType::operator()(
    const framework::OpDesc& op_desc, framework::BlockDesc* block) const {
  std::string in_reader_name = op_desc.Input("UnderlyingReader")[0];
  framework::VarDesc* in_reader = block->FindVarRecursive(in_reader_name);
  std::string out_reader_name = op_desc.Output("Out")[0];
  framework::VarDesc* out_reader = block->FindVarRecursive(out_reader_name);
  out_reader->SetType(framework::proto::VarType::READER);
  out_reader->SetDataTypes(in_reader->GetDataTypes());
}

DecoratedReaderMakerBase::DecoratedReaderMakerBase(
    framework::OpProtoAndCheckerMaker::OpProto* op_proto,
    framework::OpAttrChecker* op_checker)
    : OpProtoAndCheckerMaker(op_proto, op_checker) {
  AddInput("UnderlyingReader",
           "(ReaderHolder) The underlying reader for creating a batch reader.");
  AddOutput("Out", "(ReaderHolder) The created batch reader.");
}

}  // namespace reader

}  // namespace operators
}  // namespace paddle
