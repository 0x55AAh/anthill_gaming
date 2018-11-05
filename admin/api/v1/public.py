from anthill.platform.api.internal import RequestTimeoutError, connector
from graphene_sqlalchemy import SQLAlchemyObjectType
from anthill.framework.apps import app
from admin import models
import graphene


class ServiceMetadata(graphene.ObjectType):
    """Service metadata entry."""

    name = graphene.String()
    title = graphene.String()
    description = graphene.String()
    icon_class = graphene.String()
    color = graphene.String()
    version = graphene.String()
    debug = graphene.Boolean()

    def __lt__(self, other):
        return self.name < other.name


class RootQuery(graphene.ObjectType):
    """Api root query."""

    services_metadata = graphene.List(ServiceMetadata, description='List of services metadata.')

    @staticmethod
    async def resolve_services_metadata(root, info, **kwargs):
        services_metadata = []
        try:
            services = await connector.internal_request('discovery', method='get_services')
        except RequestTimeoutError:
            pass
        else:
            for name in services.keys():
                if name == app.name:
                    # Skip current application
                    continue
                try:
                    metadata = await connector.internal_request(name, method='get_service_metadata')
                    services_metadata.append(ServiceMetadata(**metadata))
                except RequestTimeoutError:
                    pass
            services_metadata.sort()
        return services_metadata


class Mutation(graphene.ObjectType):
    pass


# noinspection PyTypeChecker
schema = graphene.Schema(query=RootQuery)
