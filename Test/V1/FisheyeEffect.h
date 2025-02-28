#ifndef FISHEYE_EFFECT_H
#define FISHEYE_EFFECT_H

#include <fstream>
#include <opencv2/opencv.hpp>
#include <libInterpolate/Interpolators/_2D/BilinearInterpolator.hpp>
#include <libInterpolate/Interpolators/_2D/BicubicInterpolator.hpp>
#include <libInterpolate/Interpolators/_2D/ThinPlateSplineInterpolator.hpp>


template <typename T>
const T& clamp(const T& v, const T& lo, const T& hi) {
    return std::max(lo, std::min(v, hi));
}

namespace _2D {
    class BilinearInterp : public BilinearInterpolator<double>
    {
    public:
        VectorType getX() { return *(this->X); }
        VectorType getY() { return *(this->Y); }
        MatrixType getZ() { return *(this->Z); }
    };

    class BicubicInterp : public BicubicInterpolator<double>
    {
    public:
        VectorType getX() { return *(this->X); }
        VectorType getY() { return *(this->Y); }
        MatrixType getZ() { return *(this->Z); }
    };
    class ThinPlateSplineInter : public ThinPlateSplineInterpolator<double>
    {
    public:
        VectorType getX() { return *(this->X); }
        VectorType getY() { return *(this->Y); }
        MatrixType getZ() { return *(this->Z); }
    };
}

// Struct to represent a 2x2 or 4x4 array of rectangles
struct RectPoints {
    cv::Point   cornersPoint[4][4];  // Image Point Index
    cv::Point2f cornersMap[4][4];    // Distorsion Map Value
    int cornersIdx[4][4];            // Grid Map Index
    // For Billinear
    // Top-Left     -  00
    // Top-Right    -  01
    // Bottom-Left  -  10
    // Bottom-Right -  11

    // For Bicubic
    // Top-Left     -  00
    // Top-Right    -  03
    // Bottom-Left  -  30
    // Bottom-Right -  33
};





struct PointCompare {
    bool operator()(const cv::Point& a, const cv::Point& b) const {
        if (a.x < b.x) return true;
        if (a.x > b.x) return false;
        return a.y < b.y;
    }
};
void SaveImage(const cv::Mat& image, const std::string& windowName);
void displayAndSaveImage(const cv::Mat& image, const std::string& windowName);
cv::Mat computeDistortionMagnitude(const cv::Mat& grid_x, const cv::Mat& grid_y);
void Generate_FixedGrid(const cv::Mat& magnitude_of_distortion, std::vector<cv::Point>& GDC_Grid_Points, const int Grid_x, const int Grid_y);
void Generate_FixedGridMap(cv::Size ImageSize, std::map<cv::Point, cv::Point2f, PointCompare>& GDC_Grid_Points, const int Grid_x, const int Grid_y);
void Generate_AdaptiveGridMap(const cv::Mat& magnitude_of_distortion, std::map<cv::Point, cv::Point2f, PointCompare>& GDC_Adaptive_Grid_Points, const int Grid_x, const int Grid_y, const float LowThreshold);
void DrawGrid(cv::Mat mSrc, const int Grid_X, const int Grid_Y);
void drawGridPoints(const std::vector<cv::Point>& gridPoints, cv::Mat& image, const cv::Scalar& color, int radius, int thickness);
void drawGridPoints(const std::map<cv::Point, cv::Point2f, PointCompare>& GDC_Adaptive_Grid_Points, cv::Mat& image, const cv::Scalar& color, int radius, int thickness);
bool findGridPointValue(const std::map<cv::Point, cv::Point2f, PointCompare>& gridPoints, const cv::Point& searchPoint, cv::Point2f& outCorrectedPoint);
bool getTileRectMap(const cv::Point& pt, const cv::Size& imageSize, const cv::Point& gridSize, const std::map<cv::Point, cv::Point2f, PointCompare>& GDC_Adaptive_Grid_Points, RectPoints& cellRect);
bool getTileRectMap4x4(const cv::Point& pt, const cv::Size& imageSize, const cv::Point& gridSize, const std::map<cv::Point, cv::Point2f, PointCompare>& GDC_Adaptive_Grid_Points, RectPoints& cellRect, RectPoints& cellRectAdaptive);
bool getTileRectMapFixed(const cv::Point& pt, const cv::Size& imageSize, const cv::Point& gridSize, std::map<cv::Point, cv::Point2f, PointCompare> GDC_Fixed_Grid_Points, RectPoints& cellRect);
cv::Point2f bilinearInterpolate(const cv::Point& pt, const RectPoints& cellRect);
void segmentDistortionMap(const cv::Mat& magnitude_of_distortion, cv::Mat& outputMask, double lowThreshold, double highThreshold);
// Function to display and save an image
void displayAndSaveImage(const cv::Mat& image, const std::string& windowName, const bool SaveCSV);

static void writeCSV(std::string filename, cv::Mat m)
{
    std::ofstream myfile;
    myfile.open(filename.c_str());
    myfile << cv::format(m, cv::Formatter::FMT_CSV) << std::endl;
    myfile.close();
}
// ![get-psnr]
static double getPSNR(const cv::Mat& I1, const cv::Mat& I2)
{
    using namespace cv;
    cv::Mat s1;
    cv::absdiff(I1, I2, s1);       // |I1 - I2|
    s1.convertTo(s1, CV_32F);  // cannot make a square on 8 bits
    s1 = s1.mul(s1);           // |I1 - I2|^2

    cv::Scalar s = sum(s1);        // sum elements per channel

    double sse = s.val[0] + s.val[1] + s.val[2]; // sum channels

    if (sse <= 1e-10) // for small values return zero
        return 0;
    else
    {
        double mse = sse / (double)(I1.channels() * I1.total());
        double psnr = 10.0 * log10((255 * 255) / mse);
        return psnr;
    }
}




// Function to calculate RMSE
static double calculateRMSE(const cv::Mat& I1, const cv::Mat& I2) {
    cv::Mat diff;
    cv::absdiff(I1, I2, diff);
    diff.convertTo(diff, CV_32F);
    diff = diff.mul(diff); // Square the difference

    cv::Scalar s = cv::sum(diff);
    double sse = s.val[0] + s.val[1] + s.val[2];

    if (sse <= 1e-10) {
        return 0.0;
    }
    else {
        double mse = sse / (double)(I1.channels() * I1.total());
        return std::sqrt(mse);
    }
}
// ![get-psnr]

class FisheyeEffect {
public:

    // Interpolation methods
    enum class InterpolationMethod {
        NEAREST_NEIGHBOR,
        BILINEAR,
        BICUBIC
    };

    // Constructor 
    FisheyeEffect(const cv::Size& imageSize);

    // Destructor
    ~FisheyeEffect();

    // Apply the fisheye effect to an image
    void applyDistortion(const cv::Mat& srcImage, cv::Mat& dstImage, int interpolation, int borderMode = cv::BORDER_CONSTANT);

    // Update distortion parameters
    void updateParameters();

    // Accessors for parameters (add as needed)
    double getFx() const { return fx; }
    void setFx(double newFx) { fx = newFx; updateParameters(); }
    // ... Similar accessors for other parameters (fy, cx, cy, k1, k2, p1, p2)

    // Generates distortion maps
    void generateDistortionMaps(double distStrength);
    void computeDistortionMapsfromFixedGrid(cv::Point Grid, const double distStrength);
    void generateDistortionMapsfromFixedGrid(
        const cv::Size& imageSize,
        const cv::Point& gridSize,
        const double distStrength,
        const std::vector<std::vector<cv::Point>>& GDC_Fixed_Grid_Points,
        std::vector<std::vector<cv::Point2f>>& GDC_Fixed_Grid_Map,
        cv::Mat& mapX,
        cv::Mat& mapY,
        InterpolationMethod method = InterpolationMethod::BILINEAR);

    void generateDistortionMapsfromFixedGridCV(
        const cv::Size& imageSize,
        const cv::Point& gridSize,
        const double distStrength,
        const std::vector<std::vector<cv::Point>>& GDC_Fixed_Grid_Points,
        std::vector<std::vector<cv::Point2f>>& GDC_Fixed_Grid_Map,
        cv::Mat& mapX,
        cv::Mat& mapY,
        InterpolationMethod method = InterpolationMethod::BILINEAR);

    void generateDistortionMapsfromAdaptiveGridMap(
        const cv::Size& imageSize,
        const cv::Point& gridSize,
        const double distStrength,
        std::map<cv::Point, cv::Point2f, PointCompare>& GDC_Adaptive_Grid_Points,
        cv::Mat& mapX,
        cv::Mat& mapY,
        InterpolationMethod method= InterpolationMethod::BILINEAR
    );

    void computeDistortionMapsfromAdaptiveGridMap(cv::Point GridSize, const double distStrength, const float LowThreshold);

    void updateDistorsionMap();
    void testFunction(cv::Mat& image, const std::vector<std::vector<cv::Point2f>>& GDC_Fixed_Grid_Map);

    void computeDistortionMapfromFixedGrid(cv::Point Grid);
    void Generate_FixedGrid(cv::Size ImageSize, std::vector<std::vector<cv::Point>>& GDC_Grid_Points, const int Grid_x, const int Grid_y);
    void generateDistortionMapsfromFixedGridMap(
        const cv::Size& imageSize,
        const cv::Point& gridSize,
        const double distStrength,
        std::map<cv::Point, cv::Point2f, PointCompare>& GDC_Grid_Points,
        cv::Mat& mapX,
        cv::Mat& mapY,
        InterpolationMethod method = InterpolationMethod::BILINEAR
    );

    void computeDistortionMapsfromFixedGridMap(const cv::Size& imageSize, cv::Point GridSize, const double distStrength);
        // Function to return distortion maps
    void getDistortionMaps(cv::Mat& out_mapX, cv::Mat& out_mapY) const {
        out_mapX = mapX.clone();
        out_mapY = mapY.clone();
    }

    double compareDistortionMaps(
        const cv::Mat& mapX1,
        const cv::Mat& mapY1,
        const cv::Mat& mapX2,
        const cv::Mat& mapY2,
        const std::string Name
    );

private:
    // Image properties
    cv::Size imageSize;

    // Distortion parameters
    double fx, fy, cx, cy;
    double k1, k2, p1, p2;

    // OpenCV matrices
    cv::Mat cameraMatrix;
    cv::Mat distCoeffs;
    cv::Mat newCameraMatrix;
    cv::Mat mapX, mapY;
    bool bUseGeneratedMaps;
    // Helper functions
    void initDistortionParameters();
    void constructMatrices();
    
    void InitUndistortRectifyMap(
        const cv::Mat& cameraMatrix,
        const cv::Mat& distCoeffs,
        const cv::Mat& R,
        const cv::Mat& newCameraMatrix,
        const cv::Size& imageSize,
        int m1type,
        cv::Mat& mapX,
        cv::Mat& mapY);

    void InitUndistortRectifyGridMap(
        const cv::Mat& cameraMatrix,
        const cv::Mat& distCoeffs,
        const cv::Mat& R,
        const cv::Mat& newCameraMatrix,
        const cv::Size& imageSize,
        const std::vector<std::vector<cv::Point>>& GDC_Fixed_Grid_Points,
        std::vector<std::vector<cv::Point2f>>& GDC_Fixed_Grid_Map,
        cv::Mat& mapX,
        cv::Mat& mapY);
};

#endif // FISHEYE_EFFECT_H
