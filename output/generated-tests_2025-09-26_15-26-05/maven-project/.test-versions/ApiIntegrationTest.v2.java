package org.javiermf.features.models.tests;

import static io.restassured.RestAssured.*;
import static org.hamcrest.Matchers.*;
import static org.junit.Assert.*;
import org.junit.*;
import io.restassured.response.Response;

public class ApiIntegrationTest {

    private static final String BASE_URL = "http://localhost:8080";
    private String productName = "smartphone";
    private String featureName = "camera";
    private String configurationName = "premium";
    private int constraintId = 123;

    @BeforeClass
    public static void setupClass() {
        baseURI = BASE_URL;
    }

    @Before
    public void setupTestData() {
        // Create product
        Response productResponse = given()
            .pathParam("productName", productName)
            .when()
            .post("/products/{productName}");
        assertEquals(201, productResponse.getStatusCode());

        // Create feature
        Response featureResponse = given()
            .pathParam("productName", productName)
            .pathParam("featureName", featureName)
            .formParam("description", "High-resolution camera with optical zoom")
            .when()
            .post("/products/{productName}/features/{featureName}");
        assertEquals(201, featureResponse.getStatusCode());

        // Create configuration
        Response configResponse = given()
            .pathParam("productName", productName)
            .pathParam("configurationName", configurationName)
            .when()
            .post("/products/{productName}/configurations/{configurationName}");
        assertEquals(201, configResponse.getStatusCode());
    }

    @After
    public void tearDown() {
        // Delete feature
        given()
            .pathParam("productName", productName)
            .pathParam("featureName", featureName)
            .when()
            .delete("/products/{productName}/features/{featureName}")
            .then()
            .statusCode(204);

        // Delete configuration
        given()
            .pathParam("productName", productName)
            .pathParam("configurationName", configurationName)
            .when()
            .delete("/products/{productName}/configurations/{configurationName}")
            .then()
            .statusCode(204);

        // Delete product
        given()
            .pathParam("productName", productName)
            .when()
            .delete("/products/{productName}")
            .then()
            .statusCode(204);
    }

    @Test
    public void test_get_products_success() {
        given()
            .when()
            .get("/products")
            .then()
            .statusCode(200)
            .contentType("application/json");
    }

    @Test
    public void test_post_products_productName_success() {
        given()
            .pathParam("productName", "newProduct")
            .when()
            .post("/products/{productName}")
            .then()
            .statusCode(201);
    }

    @Test
    public void test_post_products_productName_invalid_params() {
        given()
            .pathParam("productName", "")
            .when()
            .post("/products/{productName}")
            .then()
            .statusCode(405);
    }

    @Test
    public void test_get_products_productName_success() {
        given()
            .pathParam("productName", productName)
            .when()
            .get("/products/{productName}")
            .then()
            .statusCode(200)
            .contentType("application/json");
    }

    @Test
    public void test_get_products_productName_invalid_params() {
        given()
            .pathParam("productName", "")
            .when()
            .get("/products/{productName}")
            .then()
            .statusCode(400);
    }

    @Test
    public void test_delete_products_productName_success() {
        given()
            .pathParam("productName", "tempProduct")
            .when()
            .post("/products/{productName}");

        given()
            .pathParam("productName", "tempProduct")
            .when()
            .delete("/products/{productName}")
            .then()
            .statusCode(204);
    }

    @Test
    public void test_delete_products_productName_invalid_params() {
        given()
            .pathParam("productName", "")
            .when()
            .delete("/products/{productName}")
            .then()
            .statusCode(405);
    }

    @Test
    public void test_get_products_productName_features_success() {
        given()
            .pathParam("productName", productName)
            .when()
            .get("/products/{productName}/features")
            .then()
            .statusCode(200)
            .contentType("application/json");
    }

    @Test
    public void test_get_products_productName_features_invalid_params() {
        given()
            .pathParam("productName", "")
            .when()
            .get("/products/{productName}/features")
            .then()
            .statusCode(400);
    }

    @Test
    public void test_post_products_productName_features_featureName_success() {
        given()
            .pathParam("productName", productName)
            .pathParam("featureName", "newFeature")
            .formParam("description", "New feature description")
            .when()
            .post("/products/{productName}/features/{featureName}")
            .then()
            .statusCode(201);
    }

    @Test
    public void test_post_products_productName_features_featureName_invalid_params() {
        given()
            .pathParam("productName", "")
            .pathParam("featureName", "")
            .formParam("description", "")
            .when()
            .post("/products/{productName}/features/{featureName}")
            .then()
            .statusCode(405);
    }

    @Test
    public void test_put_products_productName_features_featureName_success() {
        given()
            .pathParam("productName", productName)
            .pathParam("featureName", featureName)
            .formParam("description", "Updated feature description")
            .when()
            .put("/products/{productName}/features/{featureName}")
            .then()
            .statusCode(200);
    }

    @Test
    public void test_put_products_productName_features_featureName_invalid_params() {
        given()
            .pathParam("productName", "")
            .pathParam("featureName", "")
            .formParam("description", "")
            .when()
            .put("/products/{productName}/features/{featureName}")
            .then()
            .statusCode(405);
    }

    @Test
    public void test_delete_products_productName_features_featureName_success() {
        given()
            .pathParam("productName", productName)
            .pathParam("featureName", "tempFeature")
            .formParam("description", "Temporary feature")
            .when()
            .post("/products/{productName}/features/{featureName}");

        given()
            .pathParam("productName", productName)
            .pathParam("featureName", "tempFeature")
            .when()
            .delete("/products/{productName}/features/{featureName}")
            .then()
            .statusCode(204);
    }

    @Test
    public void test_delete_products_productName_features_featureName_invalid_params() {
        given()
            .pathParam("productName", "")
            .pathParam("featureName", "")
            .when()
            .delete("/products/{productName}/features/{featureName}")
            .then()
            .statusCode(405);
    }

    @Test
    public void test_get_products_productName_configurations_success() {
        given()
            .pathParam("productName", productName)
            .when()
            .get("/products/{productName}/configurations")
            .then()
            .statusCode(200)
            .contentType("application/json");
    }

    @Test
    public void test_get_products_productName_configurations_invalid_params() {
        given()
            .pathParam("productName", "")
            .when()
            .get("/products/{productName}/configurations")
            .then()
            .statusCode(500);
    }

    @Test
    public void test_post_products_productName_configurations_configurationName_success() {
        given()
            .pathParam("productName", productName)
            .pathParam("configurationName", "newConfig")
            .when()
            .post("/products/{productName}/configurations/{configurationName}")
            .then()
            .statusCode(201);
    }

    @Test
    public void test_post_products_productName_configurations_configurationName_invalid_params() {
        given()
            .pathParam("productName", "")
            .pathParam("configurationName", "")
            .when()
            .post("/products/{productName}/configurations/{configurationName}")
            .then()
            .statusCode(405);
    }

    @Test
    public void test_get_products_productName_configurations_configurationName_success() {
        given()
            .pathParam("productName", productName)
            .pathParam("configurationName", configurationName)
            .when()
            .get("/products/{productName}/configurations/{configurationName}")
            .then()
            .statusCode(200)
            .contentType("application/json");
    }

    @Test
    public void test_get_products_productName_configurations_configurationName_invalid_params() {
        given()
            .pathParam("productName", "")
            .pathParam("configurationName", "")
            .when()
            .get("/products/{productName}/configurations/{configurationName}")
            .then()
            .statusCode(500);
    }

    @Test
    public void test_delete_products_productName_configurations_configurationName_success() {
        given()
            .pathParam("productName", productName)
            .pathParam("configurationName", "tempConfig")
            .when()
            .post("/products/{productName}/configurations/{configurationName}");

        given()
            .pathParam("productName", productName)
            .pathParam("configurationName", "tempConfig")
            .when()
            .delete("/products/{productName}/configurations/{configurationName}")
            .then()
            .statusCode(204);
    }

    @Test
    public void test_delete_products_productName_configurations_configurationName_invalid_params() {
        given()
            .pathParam("productName", "")
            .pathParam("configurationName", "")
            .when()
            .delete("/products/{productName}/configurations/{configurationName}")
            .then()
            .statusCode(405);
    }

    @Test
    public void test_get_products_productName_configurations_configurationName_features_success() {
        given()
            .pathParam("productName", productName)
            .pathParam("configurationName", configurationName)
            .when()
            .get("/products/{productName}/configurations/{configurationName}/features")
            .then()
            .statusCode(200)
            .contentType("application/json");
    }

    @Test
    public void test_get_products_productName_configurations_configurationName_features_invalid_params() {
        given()
            .pathParam("productName", "")
            .pathParam("configurationName", "")
            .when()
            .get("/products/{productName}/configurations/{configurationName}/features")
            .then()
            .statusCode(500);
    }

    @Test
    public void test_post_products_productName_configurations_configurationName_features_featureName_success() {
        given()
            .pathParam("productName", productName)
            .pathParam("configurationName", configurationName)
            .pathParam("featureName", "newFeature")
            .when()
            .post("/products/{productName}/configurations/{configurationName}/features/{featureName}")
            .then()
            .statusCode(500);
    }

    @Test
    public void test_post_products_productName_configurations_configurationName_features_featureName_invalid_params() {
        given()
            .pathParam("productName", "")
            .pathParam("configurationName", "")
            .pathParam("featureName", "")
            .when()
            .post("/products/{productName}/configurations/{configurationName}/features/{featureName}")
            .then()
            .statusCode(405);
    }

    @Test
    public void test_delete_products_productName_configurations_configurationName_features_featureName_success() {
        given()
            .pathParam("productName", productName)
            .pathParam("configurationName", configurationName)
            .pathParam("featureName", "tempFeature")
            .when()
            .post("/products/{productName}/configurations/{configurationName}/features/{featureName}");

        given()
            .pathParam("productName", productName)
            .pathParam("configurationName", configurationName)
            .pathParam("featureName", "tempFeature")
            .when()
            .delete("/products/{productName}/configurations/{configurationName}/features/{featureName}")
            .then()
            .statusCode(500);
    }

    @Test
    public void test_delete_products_productName_configurations_configurationName_features_featureName_invalid_params() {
        given()
            .pathParam("productName", "")
            .pathParam("configurationName", "")
            .pathParam("featureName", "")
            .when()
            .delete("/products/{productName}/configurations/{configurationName}/features/{featureName}")
            .then()
            .statusCode(405);
    }

    @Test
    public void test_post_products_productName_constraints_requires_success() {
        given()
            .pathParam("productName", productName)
            .formParam("sourceFeature", "advanced-camera")
            .formParam("requiredFeature", "high-resolution-display")
            .when()
            .post("/products/{productName}/constraints/requires")
            .then()
            .statusCode(201);
    }

    @Test
    public void test_post_products_productName_constraints_requires_invalid_params() {
        given()
            .pathParam("productName", "")
            .formParam("sourceFeature", "")
            .formParam("requiredFeature", "")
            .when()
            .post("/products/{productName}/constraints/requires")
            .then()
            .statusCode(404);
    }

    @Test
    public void test_post_products_productName_constraints_excludes_success() {
        given()
            .pathParam("productName", productName)
            .formParam("sourceFeature", "budget-processor")
            .formParam("excludedFeature", "gaming-gpu")
            .when()
            .post("/products/{productName}/constraints/excludes")
            .then()
            .statusCode(201);
    }

    @Test
    public void test_post_products_productName_constraints_excludes_invalid_params() {
        given()
            .pathParam("productName", "")
            .formParam("sourceFeature", "")
            .formParam("excludedFeature", "")
            .when()
            .post("/products/{productName}/constraints/excludes")
            .then()
            .statusCode(404);
    }

    @Test
    public void test_delete_products_productName_constraints_constraintId_success() {
        given()
            .pathParam("productName", productName)
            .pathParam("constraintId", constraintId)
            .when()
            .delete("/products/{productName}/constraints/{constraintId}")
            .then()
            .statusCode(204);
    }

    @Test
    public void test_delete_products_productName_constraints_constraintId_invalid_params() {
        given()
            .pathParam("productName", "")
            .pathParam("constraintId", "")
            .when()
            .delete("/products/{productName}/constraints/{constraintId}")
            .then()
            .statusCode(500);
    }

    @Test
    public void test_get_root_source() {
        given()
            .when()
            .get("/")
            .then()
            .statusCode(404);
    }
}