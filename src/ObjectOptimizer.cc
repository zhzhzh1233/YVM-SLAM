/**
* This file is part of ORB-SLAM3
*
* Copyright (C) 2017-2021 Carlos Campos, Richard Elvira, Juan J. Gómez Rodríguez, José M.M. Montiel and Juan D. Tardós, University of Zaragoza.
* Copyright (C) 2014-2016 Raúl Mur-Artal, José M.M. Montiel and Juan D. Tardós, University of Zaragoza.
*
* ORB-SLAM3 is free software: you can redistribute it and/or modify it under the terms of the GNU General Public
* License as published by the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* ORB-SLAM3 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
* the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License along with ORB-SLAM3.
* If not, see <http://www.gnu.org/licenses/>.
*/

#include "ObjectOptimizer.h"

#include <gtsam/geometry/Point3.h>
#include <gtsam/nonlinear/LevenbergMarquardtOptimizer.h>
#include <gtsam/nonlinear/NonlinearFactorGraph.h>
#include <gtsam/nonlinear/Values.h>
#include <gtsam/slam/PriorFactor.h>

#include <chrono>
#include "DebugFlags.h"

namespace ORB_SLAM3
{

ObjectOptimizer::ObjectOptimizer(Atlas* pAtlas)
    : mpAtlas(pAtlas), mbStop(false), mbFinished(false)
{
}

void ObjectOptimizer::Run()
{
    mbFinished.store(false, std::memory_order_relaxed);
    mbStop.store(false, std::memory_order_relaxed);

    while (!mbStop.load(std::memory_order_relaxed))
    {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        Optimize();
    }

    mbFinished.store(true, std::memory_order_relaxed);
}

void ObjectOptimizer::Optimize()
{
    if (!mpAtlas)
        return;

    Map* pMap = mpAtlas->GetCurrentMap();
    if (!pMap)
        return;

    const std::vector<MapObject*> objects = pMap->GetAllMapObjects();
    if (objects.empty())
        return;

    const auto noise_model = gtsam::noiseModel::Isotropic::Sigma(3, 0.1);

    for (MapObject* obj : objects)
    {
        if (!obj)
            continue;

        const std::vector<cv::Point3f> observations = obj->GetObservations();
        if (observations.size() < 5)
            continue;

        gtsam::NonlinearFactorGraph graph;
        gtsam::Values initial_estimate;
        const gtsam::Key key = 1;

        for (const auto& obs : observations)
        {
            graph.add(gtsam::PriorFactor<gtsam::Point3>(
                key, gtsam::Point3(obs.x, obs.y, obs.z), noise_model));
        }

        const cv::Point3f curr = obj->GetPosWorld();
        initial_estimate.insert(key, gtsam::Point3(curr.x, curr.y, curr.z));

        try
        {
            gtsam::LevenbergMarquardtOptimizer optimizer(graph, initial_estimate);
            const gtsam::Values result = optimizer.optimize();
            const gtsam::Point3 opt = result.at<gtsam::Point3>(key);
            obj->SetPosWorld(cv::Point3f(opt.x(), opt.y(), opt.z()));
            if (gLogGTSAM.load(std::memory_order_relaxed))
                std::cout << "[GTSAM] Obj id=" << obj->Id()
                          << " obs=" << observations.size()
                          << " pos=(" << opt.x() << "," << opt.y() << "," << opt.z() << ")"
                          << std::endl;
        }
        catch (...)
        {
            continue;
        }
    }
}

void ObjectOptimizer::RequestStop()
{
    mbStop.store(true, std::memory_order_relaxed);
}

bool ObjectOptimizer::IsFinished() const
{
    return mbFinished.load(std::memory_order_relaxed);
}

} // namespace ORB_SLAM3
